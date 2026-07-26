/**
 * screens/ProjectContext.tsx — AUTOMATA project workspace view.
 *
 * Owns: showing recent project memory and actions for the selected project.
 * Never: talks to CockroachDB or Bedrock directly.
 */

import { useState, useEffect } from "react";
import { getMorningBrief, restoreWorkspace, continuePreviousWork, generateProjectSummary, startDevEnvironment, explainRepository, type MorningBrief, type RestoreStep } from "../lib/api";

interface ProjectContextProps {
  projectId: string;
  onBack: () => void;
}

export default function ProjectContext({ projectId, onBack }: ProjectContextProps) {
  const [brief, setBrief] = useState<MorningBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [restoring, setRestoring] = useState(false);
  const [restoreResult, setRestoreResult] = useState<{ steps: RestoreStep[]; overall: string } | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [lastAction, setLastAction] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getMorningBrief(projectId)
      .then(({ brief }) => {
        if (!cancelled) setBrief(brief);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unknown error");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true };
  }, [projectId]);

  const handleRestore = async () => {
    setRestoring(true);
    setRestoreResult(null);
    try {
      const result = await restoreWorkspace(projectId);
      setRestoreResult({ steps: result.steps, overall: result.overall ?? "error" });
    } catch (err: unknown) {
      setRestoreResult({ steps: [], overall: "error" });
    } finally {
      setRestoring(false);
    }
  };

  const runAction = async (label: string, action: () => Promise<unknown>) => {
    if (actionLoading) return;
    setActionLoading(label);
    setLastAction(null);
    try {
      await action();
      setLastAction(`${label} completed`);
    } catch (err: unknown) {
      setLastAction(`${label} failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="automata-loading" role="status" aria-live="polite">
        <span className="automata-spinner" aria-hidden="true" />
        <p>Loading project context…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="automata-error" role="alert">
        <p>Could not load project context</p>
        <p>{error}</p>
        <button onClick={onBack} style={{ marginTop: "0.75rem" }}>Back</button>
      </div>
    );
  }

  const ready = (brief?.highlights?.length || 0) > 0 || (brief?.pending_items?.length || 0) > 0 || (brief?.commits_count || 0) > 0;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
        <button
          id="project-back-btn"
          onClick={onBack}
          style={{
            padding: "0.4rem 0.7rem",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--color-border-soft)",
            background: "transparent",
            color: "var(--color-text-secondary)",
            cursor: "pointer",
          }}
        >
          ← Back
        </button>
        <h2 style={{ margin: 0 }}>Project workspace</h2>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <section className="brief-section">
          <h3>Restore</h3>
          <p style={{ opacity: 0.8 }}>Reopen your last workspace state: git branch, terminal, editor, and servers.</p>
          <button
            id="restore-workspace-btn"
            className="automata-btn-primary"
            onClick={handleRestore}
            disabled={restoring}
          >
            {restoring ? "Restoring…" : "Restore workspace"}
          </button>
          {restoreResult && (
            <div style={{ marginTop: "0.75rem" }}>
              <p><strong>Overall:</strong> {restoreResult.overall}</p>
              {restoreResult.steps.map((step) => (
                <div key={step.step} style={{ fontSize: "0.8rem", opacity: 0.9 }}>
                  {step.step}: {step.status} {step.detail ? `— ${step.detail}` : ""}
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="brief-section">
          <h3>Recent activity</h3>
          {!ready && <p>No highlights or pending items yet.</p>}
          {brief?.highlights?.length ? (
            <div>
              <h4 style={{ marginBottom: "0.25rem" }}>Highlights</h4>
              <ul>
                {brief.highlights.map((h, i) => <li key={i}>{h}</li>)}
              </ul>
            </div>
          ) : null}
          {brief?.pending_items?.length ? (
            <div>
              <h4 style={{ marginBottom: "0.25rem" }}>Pending</h4>
              <ul>
                {brief.pending_items.map((p, i) => <li key={i}>{p}</li>)}
              </ul>
            </div>
          ) : null}
          <p style={{ fontSize: "0.8rem", opacity: 0.7 }}>
            {brief?.commits_count ?? 0} commits · last edited: {brief?.last_edited_file || "unknown"}
          </p>
        </section>

        <section className="brief-section">
          <h3>Actions</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <button
              id="action-continue"
              className="automata-btn-primary"
              disabled={!!actionLoading}
              onClick={() => runAction("Continue previous work", () => continuePreviousWork(projectId))}
            >
              {actionLoading === "Continue previous work" ? "Planning…" : "Continue previous work"}
            </button>
            <button
              id="action-summary"
              className="automata-btn-primary"
              disabled={!!actionLoading}
              onClick={() => runAction("Project summary", () => generateProjectSummary(projectId))}
            >
              {actionLoading === "Project summary" ? "Summarizing…" : "Project summary"}
            </button>
            <button
              id="action-dev"
              className="automata-btn-primary"
              disabled={!!actionLoading}
              onClick={() => runAction("Start dev environment", () => startDevEnvironment(projectId))}
            >
              {actionLoading === "Start dev environment" ? "Starting…" : "Start dev environment"}
            </button>
            <button
              id="action-explain"
              className="automata-btn-primary"
              disabled={!!actionLoading}
              onClick={() => runAction("Explain repository", () => explainRepository(projectId, "./"))}
            >
              {actionLoading === "Explain repository" ? "Explaining…" : "Explain repository"}
            </button>
          </div>
          {lastAction && <p style={{ fontSize: "0.8rem", opacity: 0.85 }}>{lastAction}</p>}
        </section>
      </div>
    </div>
  );
}
