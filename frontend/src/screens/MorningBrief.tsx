/**
 * screens/MorningBrief.tsx — AUTOMATA Morning Brief screen
 *
 * Redesigned against:
 * - ui-ux-pro-max: accessibility, loading feedback, typography, spacing, motion
 * - taste-skill: restrained premium feel, no generic filler
 * - superpowers verification-before-completion: explicit loading/error states
 */

import React, { useEffect, useState } from "react";
import { getMorningBrief, getDecisions, type MorningBrief, type DecisionEntry } from "../lib/api";

interface MorningBriefProps {
  projectId: string;
}

export const MorningBriefScreen: React.FC<MorningBriefProps> = ({ projectId }) => {
  const [brief, setBrief] = useState<MorningBrief | null>(null);
  const [decisions, setDecisions] = useState<DecisionEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getMorningBrief(projectId)
      .then(({ brief }) => {
        if (!cancelled) setBrief(brief)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unknown error")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    getDecisions(projectId)
      .then(({ decisions }: { decisions: DecisionEntry[] }) => {
        if (!cancelled) setDecisions(decisions || [])
      })
      .catch(() => {
        if (!cancelled) setDecisions([])
      })
    return () => { cancelled = true }
  }, [projectId]);

  if (loading) {
    return (
      <div className="automata-loading" role="status" aria-live="polite">
        <span className="automata-spinner" aria-hidden="true" />
        <p>Loading your brief…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="automata-error" role="alert">
        <p>Could not load morning brief</p>
        <p>{error}</p>
        <p className="automata-error-hint">
          Ensure the AUTOMATA agent is running at http://127.0.0.1:8001
        </p>
      </div>
    );
  }

  if (!brief) {
    return (
      <div className="automata-empty">
        <h1>Good Morning</h1>
        <p>No brief available yet. Start a session to begin capturing memory.</p>
        <p className="automata-phase-note">
          Phase 2 will populate this from CockroachDB.
        </p>
      </div>
    );
  }

  const ready = brief.highlights.length > 0 || brief.pending_items.length > 0 || brief.commits_count > 0

  return (
    <section className="automata-morning-brief" aria-labelledby="brief-heading">
      <h1 id="brief-heading">Good Morning</h1>
      <p className="brief-date">{brief.brief_date}</p>

      <div className="brief-stats">
        <span>{brief.commits_count} commit{brief.commits_count === 1 ? '' : 's'} yesterday</span>
        {brief.last_edited_file && (
          <span>Last edited: <code>{brief.last_edited_file}</code></span>
        )}
      </div>

      {!ready && (
        <div className="automata-empty" style={{ padding: '1.5rem' }}>
          <p>No highlights or pending items yet.</p>
        </div>
      )}

      {brief.highlights.length > 0 && (
        <div className="brief-section">
          <h2>What you completed</h2>
          <ul>
            {brief.highlights.map((h, i) => <li key={i}>{h}</li>)}
          </ul>
        </div>
      )}

      {brief.pending_items.length > 0 && (
        <div className="brief-section">
          <h2>Pending work</h2>
          <ul>
            {brief.pending_items.map((p, i) => <li key={i}>{p}</li>)}
          </ul>
        </div>
      )}

      {decisions.length > 0 && (
        <div className="brief-section">
          <h2>Autonomous actions</h2>
          <ul>
              {decisions.map((d, i) => (
                <li key={d.id || i}>
                  <strong>{d.action_type}</strong>
                  {d.created_at && (
                    <span style={{ marginLeft: 8, opacity: 0.7 }}>
                      {new Date(d.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  )}
                  {d.trigger && (
                    <p style={{ margin: 0, opacity: 0.85 }}>{d.trigger}</p>
                  )}
                </li>
              ))}
          </ul>
        </div>
      )}
    </section>
  );
};

export default MorningBriefScreen;
