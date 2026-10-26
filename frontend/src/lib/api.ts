/**
 * lib/api.ts — AUTOMATA typed API client
 *
 * Owns:    All HTTP and WebSocket communication between the React frontend
 *          and the Python FastAPI backend.
 * Never:   Must not contain UI logic. Must not talk directly to CockroachDB
 *          or Bedrock — all backend calls go through this module.
 */


import type { PermissionRequest } from "./permissions";

const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");

const WS_BASE = () => {
  if (import.meta.env.VITE_WS_BASE) {
    return String(import.meta.env.VITE_WS_BASE).replace(/\/$/, "");
  }
  if (API_BASE.startsWith("https://")) return API_BASE.replace(/^https:/, "wss:");
  if (API_BASE.startsWith("http://")) return API_BASE.replace(/^http:/, "ws:");
  if (typeof window !== "undefined") {
    return `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;
  }
  return "ws://127.0.0.1:8000";
};
const WS_URL = `${WS_BASE()}/ws`;

// â”€â”€â”€ Types â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
  brief_text?: string;
  generated_at: string;
}

// â”€â”€â”€ System resources & app usage â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export interface GpuDevice {
  index: number;
  name: string | null;
  utilization_percent: number | null;
  temperature_c: number | null;
  power_watts: number | null;
  memory_used_mb: number | null;
  memory_total_mb: number | null;
  memory_percent: number | null;
}

export interface ProcessUsage {
  name: string;
  cpu_percent: number;
  memory_mb: number;
  count: number;
}

export interface SystemMetrics {
  available: boolean;
  reason?: string;
  timestamp?: number;
  cpu?: { percent: number; per_core: number[]; cores_logical: number; cores_physical: number | null; frequency_mhz: number | null };
  memory?: { percent: number; used_gb: number; total_gb: number; available_gb: number; swap_percent: number };
  gpu?: { available: boolean; reason: string | null; devices: GpuDevice[] };
  disk?: { mount: string; used_gb: number | null; total_gb: number | null; percent: number | null; read_bps: number; write_bps: number };
  network?: { recv_bps: number; sent_bps: number };
  battery?: { percent: number; plugged_in: boolean } | null;
  uptime_seconds?: number;
  history: Array<{ t: number; cpu: number; ram: number; gpu: number | null; vram: number | null }>;
  processes?: ProcessUsage[];
}

export type UsageRange = "today" | "week" | "month";

export interface UsageTrackerStatus {
  supported: boolean;
  running: boolean;
  paused: boolean;
  idle: boolean;
  current: { app: string; category: string; title: string; since: number } | null;
  disabled_by_env: boolean;
  error: string | null;
  db_path: string | null;
  idle_threshold_seconds: number;
}

export interface UsageSummary {
  range: UsageRange;
  start: number;
  end: number;
  total_seconds: number;
  focus_percent: number;
  app_switches: number;
  longest_session: { app: string; seconds: number; started_at: number } | null;
  apps: Array<{ app: string; category: string; seconds: number; sessions: number; percent: number; top_title: string }>;
  categories: Array<{ category: string; seconds: number; percent: number }>;
  hourly: Array<{ hour: number; seconds: number }>;
  daily: Array<{ day: string; seconds: number }>;
  tracking?: UsageTrackerStatus;
  error?: string;
}

export interface UsageTimeline {
  day: string;
  segments: Array<{ app: string; category: string; title: string; start: number; end: number; seconds: number }>;
}

export interface AutostartStatus {
  supported: boolean;
  enabled: boolean;
  launcher: string | null;
  command: string;
  error?: string;
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
  | "task_update"
  | "file"
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
  detail?: string;
  created_at: string;
}

export interface ActionCard {
  type?: string;
  policy?: string;
  params?: Record<string, unknown>;
  executed?: boolean;
  executed_at?: string;
  provenance?: string;
  result?: Record<string, unknown>;
}

export interface ChatResponse {
  needs_permission?: PermissionRequest;
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
  decision: string;
  rationale: string;
  decided_at: string;
}

export interface Todo {
  id: string;
  project_id: string;
  description: string;
  status: string;
  source: string;
  created_at: string;
  resolved_at: string | null;
}

export interface Session {
  id: string;
  project_id: string;
  started_at: string;
  ended_at: string | null;
  summary: string | null;
}

export interface EndSessionResult {
  ended: boolean;
  session_id: string;
  project_id: string;
  error?: string;
}

// â”€â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const target = url.startsWith("http") ? url : `${API_BASE}${url}`;
  const res = await fetch(target, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    ...init,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    let detail = "";
    try {
      const parsed = JSON.parse(text) as { detail?: unknown };
      if (typeof parsed.detail === "string") detail = parsed.detail;
    } catch {
      /* not JSON */
    }
    throw new Error(detail || `Request failed: ${res.status} ${res.statusText}${text ? ` - ${text}` : ""}`);
  }

  return res.json() as Promise<T>;
}

export interface AnalyticsData {
  project_id: string;
  commits_over_time: Array<{ day: string; count: number }>;
  file_edits_over_time: Array<{ day: string; count: number }>;
  todo_stats: { pending: number; completed: number; total: number };
  session_stats: { total_sessions: number; total_time_seconds: number };
  top_files: Array<{ file_path: string; edit_count: number }>;
}

export interface LiveMetrics {
  project_id: string;
  generated_at: string;
  agent: {
    uptime_seconds: number;
    started_at: string;
    api_latency_ms: number;
    db_status: HealthStatus["db"];
    reasoning_backend: "available" | "unavailable";
  };
  memory: {
    commits: number;
    file_edits: number;
    terminal_commands: number;
    decisions: number;
    todos_pending: number;
    todos_done: number;
    events_last_hour: number;
    failed_commands: number;
    test_commands: number;
    recent_test_failures: number;
    changed_files: number;
  };
  performance: {
    events_per_minute_last_hour: number;
    active_sessions: number;
    completion_percent: number;
    module_health: Array<{ name: string; pct: number; basis: string }>;
  };
}

export interface MemoryGraphNode {
  id: string;
  table: string;
  content: string;
  timestamp?: string;
}

export interface MemoryGraphEdge {
  source: string;
  target: string;
  type: string;
  shared_terms?: string[];
}

export interface MemoryGraphData {
  project_id: string;
  nodes: MemoryGraphNode[];
  edges: MemoryGraphEdge[];
}

// â”€â”€â”€ API functions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export async function getHealth(): Promise<HealthStatus> {
  return apiFetch<HealthStatus>("/health");
}

export async function listProjects(): Promise<{ projects: Project[] }> {
  return apiFetch<{ projects: Project[] }>("/projects");
}

export async function getProject(projectId: string): Promise<{ project: Project | null }> {
  const { projects } = await listProjects();
  return { project: projects.find((p) => p.id === projectId) ?? null };
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

export async function getProjectAnalytics(projectId: string): Promise<{ analytics: AnalyticsData }> {
  return apiFetch<{ analytics: AnalyticsData }>(`/projects/${projectId}/analytics`);
}

export async function getLiveMetrics(projectId: string): Promise<LiveMetrics> {
  return apiFetch<LiveMetrics>(`/projects/${projectId}/metrics/live`);
}

export async function getMemoryGraph(projectId: string): Promise<MemoryGraphData> {
  return apiFetch<MemoryGraphData>(`/projects/${projectId}/memory-graph`);
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

export async function sendChatMessage(message: string, projectId?: string, activeProjectId?: string, allowExecute = false, permissionId?: string): Promise<ChatResponse> {
  return apiFetch<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ message, project_id: projectId || null, active_project_id: activeProjectId || null, allow_execute: allowExecute, permission_id: permissionId }),
  });
}

export async function approveAction(actionType: string, params: Record<string, unknown>, projectId?: string, message?: string): Promise<{ action_type: string; executed: boolean; result: unknown }> {
  return apiFetch("/chat/approve-action", {
    method: "POST",
    body: JSON.stringify({ action_type: actionType, params, project_id: projectId || null, message }),
  });
}

export async function executeCommand(command: string, opts: { cwd?: string; allowExecute?: boolean; context?: string; sessionId?: string; projectId?: string } = {}): Promise<CommandExecuteResponse> {
  return apiFetch<CommandExecuteResponse>("/commands/execute", {
    method: "POST",
    body: JSON.stringify({
      command,
      cwd: opts.cwd || "",
      allow_execute: !!opts.allowExecute,
      context: opts.context || "",
      session_id: opts.sessionId || null,
      project_id: opts.projectId || null,
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

/** Todos for a project. */
export async function getTodos(projectId: string): Promise<{ todos: Todo[] }> {
  return apiFetch<{ todos: Todo[] }>(`/projects/${projectId}/todos`);
}

/** Update a todo's status. */
export async function updateTodoStatus(projectId: string, todoId: string, status: string): Promise<{ success: boolean; todo_id: string; status: string } | { error: string; success: boolean }> {
  return apiFetch(`/projects/${projectId}/todos/${todoId}/status`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
}

/** Sessions for a project. */
export async function getSessions(projectId: string): Promise<{ sessions: Session[] }> {
  return apiFetch<{ sessions: Session[] }>(`/projects/${projectId}/sessions`);
}

/** Current git branch for a project. */
export async function getGitBranch(projectId: string): Promise<{ branch: string | null; error: string | null }> {
  return apiFetch<{ branch: string | null; error: string | null }>(`/projects/${projectId}/git/branch`);
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

/** Live CPU / GPU / RAM / disk snapshot (processes are scanned only when asked). */
export async function getSystemMetrics(processes = false): Promise<SystemMetrics> {
  return apiFetch<SystemMetrics>(`/system/metrics${processes ? "?processes=true" : ""}`);
}

/** Time spent per app and category for the chosen range. */
export async function getUsageSummary(range: UsageRange): Promise<UsageSummary> {
  return apiFetch<UsageSummary>(`/usage/summary?range=${range}`);
}

/** Focus segments for one local day (default today). */
export async function getUsageTimeline(day?: string): Promise<UsageTimeline> {
  return apiFetch<UsageTimeline>(`/usage/timeline${day ? `?day=${encodeURIComponent(day)}` : ""}`);
}

export async function setUsageTracking(enabled: boolean): Promise<UsageTrackerStatus> {
  return apiFetch<UsageTrackerStatus>("/usage/tracking", {
    method: "POST",
    body: JSON.stringify({ enabled }),
  });
}

export async function getAutostart(): Promise<AutostartStatus> {
  return apiFetch<AutostartStatus>("/system/autostart");
}

export async function setAutostart(enabled: boolean): Promise<AutostartStatus> {
  return apiFetch<AutostartStatus>("/system/autostart", {
    method: "POST",
    body: JSON.stringify({ enabled }),
  });
}

// â”€â”€â”€ Smart workspace: AI setup, memory, snapshots, profile, desktop, tasks â”€â”€â”€

export interface OllamaStatus {
  installed: boolean;
  exe?: string | null;
  running: boolean;
  url?: string;
  models: string[];
  chat_model: string;
  chat_model_ready: boolean;
  embedding_model: string;
  embedding_model_ready: boolean;
}

export interface AiStatus {
  online: boolean;
  reasoning_mode: string;
  cloud_providers: Record<string, boolean>;
  ollama: OllamaStatus;
  offline_embeddings: { installed: boolean; enabled: boolean; model: string; loaded: boolean };
  last_answer: { provider: string | null; model: string | null; at: number | null };
}

export interface LocalModelInfo { name: string; size_gb: number; min_vram_gb: number; use: string; label: string }

export interface LocalRecommendation {
  chat_model: string;
  embedding_model: string;
  reason: string;
  vram_gb: number;
  models_dir: string;
  free_gb: number | null;
  needed_gb: number;
  warning: string | null;
  catalog: LocalModelInfo[];
}

export interface PullStatus {
  model: string | null;
  status: "idle" | "pulling" | "done" | "error";
  completed: number;
  total: number;
  percent: number;
  error: string | null;
}

export interface SelfCheckItem {
  key: string;
  label: string;
  ok: boolean;
  detail: string;
  fix: string | null;
  level: "ok" | "info" | "warning" | "error";
}

export interface MemoryHit {
  id: number;
  project_id: string | null;
  kind: string;
  content: string;
  timestamp: string;
  score?: number;
}

export interface SnapshotData {
  project_id: string;
  project_name?: string;
  repo_path: string;
  branch: string;
  changed_files: string[];
  last_commit: string;
  recent_files: string[];
  open_windows: Array<{ app: string; title: string; related: boolean }>;
  dev_servers: Array<{ port: number; process?: string; command?: string }>;
  open_todos: string[];
  last_chat: string | null;
  current_task: { id: string; title: string; status: string; progress: string } | null;
}

export interface Snapshot { id: number; project_id: string; created_at: number; reason: string; data: SnapshotData }

export interface ResumeResult {
  needs_permission?: PermissionRequest;
  success: boolean;
  partial?: boolean;
  error?: string;
  steps: Array<{ step: string; status: string; detail: string }>;
  summary?: { branch: string; last_commit: string; changed_files: number; open_todos: string[]; current_task: SnapshotData["current_task"] };
}

export interface ProfileModule {
  name: string;
  path: string;
  files: number;
  test_files: number;
  todos: number;
  languages: string[];
  pct: number;
  recent_edits: number;
  basis: string;
}

export interface ProjectProfile {
  ok: boolean;
  project_id: string;
  name: string;
  repo_path: string;
  summary: string;
  type: { kind: string; label: string; ai: boolean; reasons: string[]; focus: string[] };
  languages: Array<{ name: string; files: number; percent: number }>;
  frameworks: string[];
  databases: string[];
  package_managers: string[];
  infrastructure: string[];
  apps: Array<{ path: string; kind: string; frameworks: string[] }>;
  run_book: Array<{ path: string; language: string; commands: Record<string, string> }>;
  ports: number[];
  env: {
    variables: Array<{ name: string; set: boolean; has_default?: boolean; declared_in: string | null; used_in: string | null; provider: string | null; kind: string }>;
    missing: string[];
    env_file_found: boolean;
  };
  modules: ProfileModule[];
  tests: { files: number; frameworks: string[] };
  file_count: number;
  scan_ms: number;
}

export interface DesktopWindow { hwnd: number; pid: number; exe: string; title: string; app: string }

export type TaskStatus = "planned" | "running" | "waiting_approval" | "waiting_input" | "paused" | "done" | "failed" | "cancelled";

export interface TaskStep {
  id: number;
  idx: number;
  kind: string;
  title: string;
  policy: "auto" | "approval" | "input";
  status: string;
  detail: string | null;
  output: Record<string, unknown> | null;
  started_at: number | null;
  finished_at: number | null;
}

export interface NeedItem {
  id: string;
  task_id: string | null;
  project_id: string | null;
  var: string;
  kind: string;
  provider: string | null;
  title: string;
  steps: string[];
  docs_url: string | null;
  target_file: string | null;
  status: string;
  created_at: number;
}

export interface TaskSummary {
  id: string;
  project_id: string | null;
  title: string;
  request: string;
  agent: string;
  status: TaskStatus;
  current_step: number;
  created_at: number;
  updated_at: number;
  summary: string | null;
  steps_total?: number;
  steps_done?: number;
}

export interface TaskDetail extends TaskSummary { steps: TaskStep[]; needs: NeedItem[] }

export const getAiStatus = () => apiFetch<AiStatus>("/ai/status");
export const getLocalRecommendation = () => apiFetch<LocalRecommendation>("/ai/local/recommendation");
export const getPullStatus = () => apiFetch<PullStatus>("/ai/local/pull");
export const pullLocalModel = (model: string) =>
  apiFetch<PullStatus & { success: boolean; error?: string }>("/ai/local/pull", { method: "POST", body: JSON.stringify({ model }) });
export const selectLocalModel = (chat_model: string) =>
  apiFetch<{ success: boolean; chat_model: string }>("/ai/local/select", { method: "POST", body: JSON.stringify({ chat_model }) });
export const installOllama = () =>
  apiFetch<{ success: boolean; detail?: string; error?: string }>("/ai/local/install-ollama", { method: "POST" });
export const setOfflineEmbeddings = (enabled: boolean) =>
  apiFetch<{ success: boolean; error?: string }>("/ai/local/offline-embeddings", { method: "POST", body: JSON.stringify({ enabled }) });
export const getSelfCheck = () => apiFetch<{ ok: boolean; checks: SelfCheckItem[] }>("/system/self-check");

export const searchMemory = (q: string, projectId?: string) =>
  apiFetch<{ query: string; results: MemoryHit[]; message: string | null }>(
    `/memory/search?q=${encodeURIComponent(q)}${projectId ? `&project_id=${encodeURIComponent(projectId)}` : ""}`,
  );
export const getMemoryStats = (projectId?: string) =>
  apiFetch<{ counts: Record<string, number>; path: string }>(`/memory/stats${projectId ? `?project_id=${projectId}` : ""}`);

export const activateProject = (projectId: string) =>
  apiFetch<{ success: boolean; project_path?: string }>(`/projects/${projectId}/activate`, { method: "POST" });
export const takeSnapshot = (projectId: string) =>
  apiFetch<{ success: boolean; data: SnapshotData }>(`/projects/${projectId}/snapshot`, { method: "POST" });
export const getLatestSnapshot = (projectId: string) =>
  apiFetch<{ snapshot: Snapshot | null }>(`/projects/${projectId}/snapshot`);
export const resumeWorkspace = (projectId: string, opts: { open_editor?: boolean; open_terminal?: boolean; start_servers?: boolean } = {}, permissionId?: string) =>
  apiFetch<ResumeResult>(`/projects/${projectId}/resume`, { method: "POST", body: JSON.stringify({ ...opts, permission_id: permissionId }) });
export const getProjectProfile = (projectId: string, refresh = false) =>
  apiFetch<ProjectProfile>(`/projects/${projectId}/profile${refresh ? "?refresh=true" : ""}`);

export const getDesktopWindows = () => apiFetch<{ success: boolean; windows: DesktopWindow[]; error?: string }>("/desktop/windows");
export const getBrowserTabs = () =>
  apiFetch<{ success: boolean; windows: Array<{ window: DesktopWindow; tabs: Array<{ index: number; title: string; selected: boolean }> }>; error?: string }>("/desktop/tabs");
export const switchBrowserTab = (title: string) =>
  apiFetch<{ success: boolean; verified?: boolean; error?: string }>("/desktop/tabs/switch", { method: "POST", body: JSON.stringify({ title }) });

export const createTask = (request: string, agent: string, projectId?: string) =>
  apiFetch<{ success: boolean; task: TaskDetail }>("/tasks", { method: "POST", body: JSON.stringify({ request, agent, project_id: projectId || null }) });
export const listTasks = (projectId?: string) =>
  apiFetch<{ tasks: TaskSummary[] }>(`/tasks${projectId ? `?project_id=${projectId}` : ""}`);
export const getTask = (taskId: string) => apiFetch<{ task: TaskDetail }>(`/tasks/${taskId}`);
export const approveTask = (taskId: string) => apiFetch<{ success: boolean }>(`/tasks/${taskId}/approve`, { method: "POST" });
export const cancelTask = (taskId: string) => apiFetch<{ success: boolean }>(`/tasks/${taskId}/cancel`, { method: "POST" });
export interface TaskQuestion {
  id: string;
  kind: "folder" | "choice" | "text";
  question: string;
  help?: string;
  options?: string[];
  default?: string;
  required?: boolean;
  from_model?: boolean;
}
/** Answer a task's questions; an empty object accepts the defaults. */
export const answerTask = (taskId: string, answers: Record<string, string>) =>
  apiFetch<{ success: boolean; answers: Record<string, string> }>(`/tasks/${taskId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers }),
  });
export const listNeeds = (projectId?: string, refresh = false) =>
  apiFetch<{ needs: NeedItem[] }>(`/needs?${projectId ? `project_id=${projectId}&` : ""}${refresh ? "refresh=true" : ""}`);
export const resolveNeed = (needId: string, saveTo: "keyring" | "env_file" | "both" | "done" | "dismiss", value?: string) =>
  apiFetch<{ success: boolean; saved_to?: string[]; warnings?: string[] }>(`/needs/${needId}/resolve`, {
    method: "POST",
    body: JSON.stringify({ save_to: saveTo, value: value ?? null }),
  });

// â”€â”€â”€ WebSocket â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

// â”€â”€â”€ Work bar (quick assist) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export interface NowPlaying {
  ok: boolean;
  playing?: boolean;
  title?: string | null;
  artist?: string | null;
  app?: string;
  status?: string;
  error?: string;
}
export interface AssistReply {
  needs_permission?: PermissionRequest;
  handled_by: "assist" | "chat";
  intent: string;
  reply: string;
  success: boolean;
}
/** Work bar command: quick actions run locally, anything else goes to chat. */
export const runAssist = (text: string, projectId?: string, permissionId?: string) =>
  apiFetch<AssistReply>("/assist", { method: "POST", body: JSON.stringify({ text, project_id: projectId, permission_id: permissionId }) });
export const getNowPlaying = () => apiFetch<NowPlaying>("/assist/now-playing");
export const mediaControl = (action: "play_pause" | "next" | "previous" | "volume_up" | "volume_down" | "mute", permissionId?: string) =>
  apiFetch<{ success: boolean; message?: string; error?: string; now_playing?: NowPlaying; needs_permission?: PermissionRequest }>("/assist/media", {
    method: "POST", body: JSON.stringify({ action, permission_id: permissionId }),
  });
/** OCR the window you're looking at and answer — only runs when called. */
export const readScreen = (question?: string, permissionId?: string) =>
  apiFetch<{ success: boolean; answer?: string; error?: string; window?: { title: string; exe: string }; needs_permission?: PermissionRequest }>(
    "/assist/screen", { method: "POST", body: JSON.stringify({ question: question ?? "", permission_id: permissionId }) });
