/**
 * lib/api.ts — AUTOMATA typed API client
 *
 * Owns:    All HTTP and WebSocket communication between the React frontend
 *          and the Python FastAPI backend at http://127.0.0.1:8000.
 * Never:   Must not contain UI logic. Must not talk directly to CockroachDB
 *          or Bedrock — all backend calls go through this module.
 * Ref:     ARCHITECTURE.md §3.1, TECH_STACK.md "Frontend ↔ Python transport".
 *
 * Phase 0: Types and stub implementations.
 * Phase 1+: Fill in real fetch() / WebSocket calls as backend routes are implemented.
 */

const API_BASE = "http://127.0.0.1:8000";
const WS_URL   = "ws://127.0.0.1:8000/ws";

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
  step: "git_checkout" | "terminal" | "dev_servers" | "editor" | "browser";
  status: "ok" | "error" | "skipped";
  detail?: string;
}

export interface RestoreResult {
  project_id: string;
  steps: RestoreStep[];
  overall: "ok" | "partial" | "error" | "skipped";
}

export interface QueryResult {
  answer: string | null;
  memories: Record<string, unknown>[];
  grounded: boolean;
}

export interface ExplainRepositoryResult {
  project_id: string;
  repo_path: string;
  readme_summary: string;
  folder_structure: Record<string, unknown>[];
  architecture_notes: Record<string, unknown>[];
  explanation: string | null;
  error: string | null;
}

// ─── WebSocket event types ─────────────────────────────────────────────────────

export type AgentEventType =
  | "connected"
  | "restore_progress"
  | "brief_ready"
  | "autonomous_action"
  | "echo";

export interface AgentEvent {
  type: AgentEventType;
  [key: string]: unknown;
}

// ─── HTTP helpers ──────────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText} — ${path}`);
  }
  return res.json() as Promise<T>;
}

// ─── API methods ───────────────────────────────────────────────────────────────

/** Check backend health — DB and Bedrock status. */
export async function getHealth(): Promise<HealthStatus> {
  return apiFetch<HealthStatus>("/health");
}

/** List all tracked projects. */
export async function listProjects(): Promise<{ projects: Project[] }> {
  return apiFetch<{ projects: Project[] }>("/projects");
}

/** Register a new project for memory tracking. */
export async function registerProject(
  name: string,
  repoPath: string,
  remoteUrl?: string,
): Promise<{ id: string | null }> {
  return apiFetch<{ id: string | null }>("/projects", {
    method: "POST",
    body: JSON.stringify({ name, repo_path: repoPath, remote_url: remoteUrl }),
  });
}

/** Get today's morning brief for a project. */
export async function getMorningBrief(projectId: string): Promise<{ brief: MorningBrief | null }> {
  return apiFetch<{ brief: MorningBrief | null }>(`/projects/${projectId}/brief`);
}

/** Trigger workspace restoration for a project. */
export async function restoreWorkspace(projectId: string): Promise<RestoreResult> {
  return apiFetch<RestoreResult>(`/projects/${projectId}/restore`, { method: "POST" });
}

/** Ask a natural-language question against project memory. */
export async function queryMemory(
  question: string,
  projectId?: string,
): Promise<QueryResult> {
  return apiFetch<QueryResult>("/query", {
    method: "POST",
    body: JSON.stringify({ question, project_id: projectId }),
  });
}

/** Ask the agent to explain the repository structure grounded in README/folder/architecture notes. */
export async function explainRepository(projectId: string, repoPath: string): Promise<ExplainRepositoryResult> {
  return apiFetch<ExplainRepositoryResult>("/explain-repository", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, repo_path: repoPath }),
  });
}

// ─── WebSocket connection ──────────────────────────────────────────────────────

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

/** Singleton WebSocket connection — import and use across the app. */
export const agentSocket = new AgentSocket();
