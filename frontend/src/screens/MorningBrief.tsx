/**
 * screens/MorningBrief.tsx — AUTOMATA Morning Brief screen
 *
 * Phase 0: Stub screen with correct types and layout shell.
 * Phase 2: Wire to api.getMorningBrief() + real data from CockroachDB/Bedrock.
 * Ref:     PROJECT.md §7 (demo story), SKILLS.md §3 (frontend skill checklist).
 */

import React, { useEffect, useState } from "react";
import { getMorningBrief, type MorningBrief } from "../lib/api";

interface MorningBriefProps {
  projectId: string;
}

export const MorningBriefScreen: React.FC<MorningBriefProps> = ({ projectId }) => {
  const [brief, setBrief] = useState<MorningBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getMorningBrief(projectId)
      .then(({ brief }) => setBrief(brief))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return (
      <div className="automata-loading">
        <span className="automata-spinner" aria-label="Loading morning brief" />
        <p>Loading your brief…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="automata-error" role="alert">
        <p>Could not load morning brief: {error}</p>
        <p className="automata-error-hint">
          Ensure the AUTOMATA agent is running at http://127.0.0.1:8000
        </p>
      </div>
    );
  }

  if (!brief) {
    return (
      <div className="automata-empty">
        <h2>Good Morning</h2>
        <p>No brief available yet — start a session to begin capturing memory.</p>
        <p className="automata-phase-note">
          (Phase 0 stub — Phase 2 will populate this from CockroachDB)
        </p>
      </div>
    );
  }

  return (
    <section className="automata-morning-brief" aria-labelledby="brief-heading">
      <h1 id="brief-heading">Good Morning</h1>
      <p className="brief-date">{brief.brief_date}</p>

      <div className="brief-stats">
        <span>{brief.commits_count} commits yesterday</span>
        {brief.last_edited_file && (
          <span>Last edited: <code>{brief.last_edited_file}</code></span>
        )}
      </div>

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
    </section>
  );
};

export default MorningBriefScreen;
