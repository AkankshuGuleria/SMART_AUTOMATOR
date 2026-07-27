/**
 * components/MorningBriefWrapper.tsx — brief wrapper with project scoping.
 */

import { useState, useEffect } from "react";
import { getMorningBrief, generateMorningBrief, type MorningBrief } from "../lib/api";

interface MorningBriefWrapperProps {
  projectId: string;
}

export default function MorningBriefWrapper({ projectId }: MorningBriefWrapperProps) {
  const [brief, setBrief] = useState<MorningBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const fetchBrief = () => {
    setLoading(true);
    setError(null);
    getMorningBrief(projectId)
      .then(({ brief }) => { setBrief(brief); })
      .catch((err: unknown) => { setError(err instanceof Error ? err.message : "Unknown error"); })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getMorningBrief(projectId)
      .then(({ brief }) => { if (!cancelled) setBrief(brief); })
      .catch((err: unknown) => { if (!cancelled) setError(err instanceof Error ? err.message : "Unknown error"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true };
  }, [projectId]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const result = await generateMorningBrief(projectId);
      if (result.success) {
        setBrief(result.brief);
      } else {
        setError(result.brief?.toString() || "Failed to generate brief");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setGenerating(false);
    }
  };

  if (loading) return <div className="automata-loading" role="status"><span className="automata-spinner" aria-hidden="true" /><p>Loading brief…</p></div>;
  if (error) return <div className="automata-error" role="alert"><p>{error}</p><button className="automata-btn-primary" onClick={fetchBrief}>Retry</button></div>;
  if (!brief) return <div className="automata-empty"><p>No brief available yet.</p><button className="automata-btn-primary" onClick={handleGenerate} disabled={generating}>{generating ? "Generating…" : "Generate Brief"}</button></div>;

  const ready = brief.highlights.length > 0 || brief.pending_items.length > 0 || brief.commits_count > 0;

  return (
    <section className="automata-morning-brief" aria-labelledby="brief-heading">
      <div className="brief-stats">
        <span>{brief.commits_count} commits</span>
        {brief.last_edited_file && <span>Last edited: <code>{brief.last_edited_file}</code></span>}
      </div>
      {!ready && <p className="automata-empty" style={{ padding: '1.5rem' }}>No highlights or pending items yet. <button className="automata-btn-primary" onClick={handleGenerate} disabled={generating}>{generating ? "Generating…" : "Generate Brief"}</button></p>}
      {brief.highlights.length > 0 && (
        <div>
          <h2>Highlights</h2>
          <ul>{brief.highlights.map((h, i) => <li key={i}>{h}</li>)}</ul>
        </div>
      )}
      {brief.pending_items.length > 0 && (
        <div>
          <h2>Pending</h2>
          <ul>{brief.pending_items.map((p, i) => <li key={i}>{p}</li>)}</ul>
        </div>
      )}
    </section>
  );
}
