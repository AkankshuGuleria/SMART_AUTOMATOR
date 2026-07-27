/**
 * lib/api.ts — AUTOMATA typed API client
 *
 * Owns:    All HTTP and WebSocket communication between the React frontend
 *          and the Python FastAPI backend.
 * Never:   Must not contain UI logic. Must not talk directly to CockroachDB
 *          or Bedrock — all backend calls go through this module.
 */


const WS_BASE = () => {
  if (typeof window !== "undefined") {
    return `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;
  }
  return "ws://127.0.0.1:8000";
};
const WS_URL = `${WS_BASE()}/ws`;

// ─── Types ────────────────────────────────────────────────────────────────────

export interface HealthStatus {
  api: "ok" | "error";
  db: { db: "connected" | "disconnected" | "error"; reason?: string };
  bedrock: "configured" | "not_configured";
  embedding: "configured" | "not_configured";
}

export interface Project {
  id: string;
  name: string;
  repo_path: string;
  remote_url?: string;
  created_at: string;
}

export interface MorningBrief {
  project_id: string;
  brief_date: string;
  commits_count: number;
  highlights: string[];
  pending_items: string[];
  last_edited_file?: string;
  generated_at: string;
}

export interface RestoreStep {
  step: string;
  status: string;
  detail?: string;
}

export interface RestoreResult {
  project_id: string;
  steps: RestoreStep[];
  error?: string;
  overall?: string;
}

export interface QueryResult {
  answer: string;
  memories: Array<Record<string, unknown>>;
  grounded: boolean;
}

export interface ExplainRepositoryResult {
  project_id: string;
  repo_path: string;
  readme_summary: string;
  folder_structure: Array<{ path: string; type: string; notable: boolean }>;
  architecture_notes: Array<{ id: string; project_id?: string; title: string; content: string; updated_at?: string }>;
  explanation: string | null;
  error: string | null;
}

export type AgentEventType =
  | "connected"
  | "restore_progress"
  | "brief_ready"
  | "autonomous_action"
  | "echo";

export interface AgentEvent {
  type: AgentEventType;
  data: Record<string, unknown>;
  timestamp: string;
}

export interface ToolStatus {
  name: string;
  available: boolean;
  version?: string;
}

export interface ActivityItem {
  id: string;
  project_id: string;
  kind: string;
  summary: string;
  created_at: string;
}

export interface ActionCard {
  type?: string;
  policy?: string;
  executed?: boolean;
  executed_at?: string;
  provenance?: string;
}

export interface ChatResponse {
  intent: string;
  confidence: number;
  reply: string;
  actions: ActionCard[];
  executed_actions: ActionCard[];
  project_id?: string;
  error?: string;
}

export interface CommandExecuteResponse {
  command: string;
  status: string;
  executed: boolean;
  suggested: boolean;
  suggestion_reason?: string;
  exit_code: number;
  stdout: string;
  stderr: string;
  executed_at: string;
  undo_hint?: string;
}

export interface AgentActionResult {
  status: string;
  message: string;
  data?: Record<string, unknown>;
}

export interface CommitMessageResult extends AgentActionResult {}

export interface FindAuthResult extends AgentActionResult {}

export interface ContinueWorkResult extends AgentActionResult {}

export interface ProjectSummaryResult extends AgentActionResult {}

export interface StartDevEnvResult extends AgentActionResult {}

export interface CrossAppTaskResult {
  task_id: string;
  status: string;
  result?: Record<string, unknown>;
  error?: string;
}

export interface DecisionEntry {
  id: string;
  project_id: string;
  trigger: string;
  action_type: string;
  executed: boolean;
  suggested: boolean;
  created_at: string;
}

export interface EndSessionResult {
  ended: boolean;
  session_id: string;
  project_id: string;
  error?: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    ...init,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Request failed: ${res.status} ${res.statusText}${text ? ` - ${text}` : ""}`);
  }

  return res.json() as Promise<T>;
}

// ─── API functions ────────────────────────────────────────────────────────────

export async function getHealth(): Promise<HealthStatus> {
  return apiFetch<HealthStatus>("/health");
}

export async function listProjects(): Promise<{ projects: Project[] }> {
  return apiFetch<{ projects: Project[] }>("/projects");
}

export async function registerProject(
  name: string,
  repoPath: string,
  remoteUrl?: string
): Promise<{ project: Project }> {
  return apiFetch<{ project: Project }>("/projects", {
    method: "POST",
    body: JSON.stringify({ name, repo_path: repoPath, remote_url: remoteUrl }),
  });
}

export async function getMorningBrief(projectId: string): Promise<{ brief: MorningBrief | null }> {
  return apiFetch<{ brief: MorningBrief | null }>(`/projects/${projectId}/brief`);
}

export async function generateMorningBrief(projectId: string): Promise<{ success: boolean; brief: MorningBrief | null }> {
  return apiFetch<{ success: boolean; brief: MorningBrief | null }>(`/projects/${projectId}/brief/generate`, {
    method: "POST",
  });
}

export async function getReasoningMode(): Promise<{ reasoning_mode: string }> {
  return apiFetch<{ reasoning_mode: string }>("/settings/reasoning-mode");
}

export async function setReasoningMode(mode: string): Promise<{ reasoning_mode: string }> {
  return apiFetch<{ reasoning_mode: string }>("/settings/reasoning-mode", {
    method: "POST",
    body: JSON.stringify({ reasoning_mode: mode }),
  });
}

export async function restoreWorkspace(projectId: string): Promise<RestoreResult> {
  return apiFetch<RestoreResult>(`/projects/${projectId}/restore`, { method: "POST" });
}

export async function queryMemory(
  question: string,
  projectId?: string,
): Promise<QueryResult> {
  return apiFetch<QueryResult>("/query", {
    method: "POST",
    body: JSON.stringify({ question, project_id: projectId || null }),
  });
}

export async function getToolStatus(): Promise<{ tools: ToolStatus[] }> {
  return apiFetch<{ tools: ToolStatus[] }>("/tools/status");
}

export async function getActivityFeed(projectId?: string, limit = 50): Promise<{ items: ActivityItem[] }> {
  const qs = new URLSearchParams();
  if (projectId) qs.set("project_id", projectId);
  if (limit) qs.set("limit", String(limit));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<{ items: ActivityItem[] }>(`/activity/feed${suffix}`);
}

export async function sendChatMessage(message: string, projectId?: string, activeProjectId?: string, allowExecute = false): Promise<ChatResponse> {
  return apiFetch<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ message, project_id: projectId || null, active_project_id: activeProjectId || null, allow_execute: allowExecute }),
  });
}

export async function executeCommand(command: string, opts: { cwd?: string; allowExecute?: boolean; context?: string; sessionId?: string } = {}): Promise<CommandExecuteResponse> {
  return apiFetch<CommandExecuteResponse>("/commands/execute", {
    method: "POST",
    body: JSON.stringify({
      command,
      cwd: opts.cwd || "",
      allow_execute: !!opts.allowExecute,
      context: opts.context || "",
      session_id: opts.sessionId || null,
    }),
  });
}

export async function generateCommitMessage(projectId: string, repoPath: string, staged = true): Promise<CommitMessageResult> {
  return apiFetch<CommitMessageResult>(`/projects/${projectId}/generate-commit-message`, {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, repo_path: repoPath, staged }),
  });
}

export async function findAuthenticationCode(projectId: string, query = "authentication"): Promise<FindAuthResult> {
  return apiFetch<FindAuthResult>(`/projects/${projectId}/find-auth-code`, {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

export async function continuePreviousWork(projectId: string): Promise<ContinueWorkResult> {
  return apiFetch<ContinueWorkResult>(`/projects/${projectId}/continue-work`, { method: "POST" });
}

export async function generateProjectSummary(projectId: string): Promise<ProjectSummaryResult> {
  return apiFetch<ProjectSummaryResult>(`/projects/${projectId}/project-summary`, { method: "POST" });
}

export async function startDevEnvironment(projectId: string): Promise<StartDevEnvResult> {
  return apiFetch<StartDevEnvResult>(`/projects/${projectId}/start-dev-environment`, { method: "POST" });
}

export async function submitCrossAppTask(taskId: string, action: string, params: Record<string, unknown>): Promise<{ task_id: string; status: string }> {
  return apiFetch(`/cross-app/tasks`, {
    method: "POST",
    body: JSON.stringify({ task_id: taskId, action, params }),
  });
}

export async function getCrossAppTask(taskId: string): Promise<CrossAppTaskResult> {
  return apiFetch<CrossAppTaskResult>(`/cross-app/tasks/${taskId}`);
}

/** Recent decision log entries for a project. */
export async function getDecisions(projectId: string, limit = 20): Promise<{ decisions: DecisionEntry[] }> {
  return apiFetch<{ decisions: DecisionEntry[] }>(`/projects/${projectId}/decisions?limit=${limit}`);
}

/** End the active session for a project. */
export async function endSession(projectId: string, summary?: string): Promise<EndSessionResult> {
  return apiFetch<EndSessionResult>(`/projects/${projectId}/sessions/end`, {
    method: "POST",
    body: JSON.stringify(summary !== undefined ? { summary } : undefined),
  });
}

/** Explain a repository grounded in stored project memory. */
export async function explainRepository(projectId: string, repoPath: string): Promise<ExplainRepositoryResult> {
  return apiFetch<ExplainRepositoryResult>(`/projects/${projectId}/explain-repository`, {
    method: "POST",
    body: JSON.stringify({ projectId, repoPath }),
  });
}

// ─── WebSocket ────────────────────────────────────────────────────────────────

export class AgentSocket {
  private ws: WebSocket | null = null;
  private handlers: Map<AgentEventType | "*", ((event: AgentEvent) => void)[]> = new Map();

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.ws = new WebSocket(WS_URL);

    this.ws.onopen = () => {
      console.info("[AgentSocket] Connected to AUTOMATA agent");
    };

    this.ws.onmessage = (msg) => {
      try {
        const event: AgentEvent = JSON.parse(msg.data as string);
        this._dispatch(event);
      } catch {
        console.warn("[AgentSocket] Received non-JSON message:", msg.data);
      }
    };

    this.ws.onclose = () => {
      console.info("[AgentSocket] Disconnected — will not auto-reconnect in Phase 0");
    };

    this.ws.onerror = (err) => {
      console.error("[AgentSocket] WebSocket error:", err);
    };
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
  }

  /** Subscribe to a specific event type, or "*" for all events. */
  on(type: AgentEventType | "*", handler: (event: AgentEvent) => void): void {
    const existing = this.handlers.get(type) ?? [];
    this.handlers.set(type, [...existing, handler]);
  }

  private _dispatch(event: AgentEvent): void {
    const typeHandlers = this.handlers.get(event.type as AgentEventType) ?? [];
    const wildcardHandlers = this.handlers.get("*") ?? [];
    [...typeHandlers, ...wildcardHandlers].forEach((h) => h(event));
  }
}

export const agentSocket = new AgentSocket();
