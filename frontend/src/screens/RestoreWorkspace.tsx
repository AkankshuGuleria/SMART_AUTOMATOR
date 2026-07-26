/**
 * screens/RestoreWorkspace.tsx — AUTOMATA Workspace Restoration screen
 *
 * Redesigned against:
 * - ui-ux-pro-max: per-step progress, accessibility, loading feedback, touch targets
 * - taste-skill: restrained motion, premium spacing, no generic slop
 * - superpowers verification-before-completion: explicit restoring/error/empty states
 */

import React, { useState } from "react";
import { restoreWorkspace, type RestoreStep } from "../lib/api";

interface RestoreWorkspaceProps {
  projectId: string;
}

const STEP_LABELS: Record<RestoreStep["step"], string> = {
  git_checkout: "Restore Git branch",
  terminal:     "Open terminal",
  dev_servers:  "Start dev servers",
  editor:       "Launch editor",
  browser:      "Restore browser tabs",
};

const STATUS_ICON: Record<RestoreStep["status"], string> = {
  ok:      "✓",
  error:   "✗",
  skipped: "–",
};

export const RestoreWorkspaceScreen: React.FC<RestoreWorkspaceProps> = ({ projectId }) => {
  const [steps, setSteps] = useState<RestoreStep[]>([]);
  const [overall, setOverall] = useState<string | null>(null);
  const [restoring, setRestoring] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRestore = async () => {
    setRestoring(true);
    setError(null);
    setSteps([]);
    setOverall(null);

    try {
      const result = await restoreWorkspace(projectId);
      setSteps(result.steps);
      setOverall(result.overall ?? null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Restore failed");
    } finally {
      setRestoring(false);
    }
  };

  return (
    <section className="automata-restore" aria-labelledby="restore-heading">
      <h1 id="restore-heading">Restore Workspace</h1>
      <p>Resume your previous development environment in one click.</p>

      <button
        id="restore-workspace-btn"
        className="automata-btn-primary"
        onClick={handleRestore}
        disabled={restoring}
        aria-busy={restoring}
      >
        {restoring ? "Restoring…" : "Restore Workspace"}
      </button>

      {error && (
        <div className="automata-error" role="alert">
          {error}
        </div>
      )}

      {steps.length > 0 && (
        <div className="restore-steps" aria-label="Restoration progress">
          {steps.map((step) => (
            <div
              key={step.step}
              className={`restore-step restore-step--${step.status}`}
            >
              <span className="step-icon" aria-hidden="true">
                {STATUS_ICON[step.status]}
              </span>
              <span className="step-label">{STEP_LABELS[step.step]}</span>
              {step.detail && (
                <span className="step-detail">{step.detail}</span>
              )}
            </div>
          ))}

          {overall && (
            <p className={`restore-overall restore-overall--${overall}`} aria-live="polite">
              {overall === "ok"      && "Workspace restored successfully."}
              {overall === "partial" && "Workspace partially restored — some steps failed. Check details above."}
              {overall === "error"   && "Restoration failed. The agent is still available for queries."}
              {overall === "skipped" && "Phase 0 stub — implement Automation Layer in Phase 3."}
            </p>
          )}
        </div>
      )}

      {!restoring && steps.length === 0 && !error && (
        <p className="automata-phase-note" style={{ marginTop: '1rem' }}>
          Restoration will replay your last workspace state step by step.
        </p>
      )}
    </section>
  );
};

export default RestoreWorkspaceScreen;
