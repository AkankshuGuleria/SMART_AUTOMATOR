/**
 * components/ProjectList.tsx — AUTOMATA project list with live status.
 */

import { useState, useEffect } from "react";
import { listProjects, getMorningBrief, type Project, type MorningBrief } from "../lib/api";

interface ProjectListProps {
  onOpen: (projectId: string) => void;
}

export default function ProjectList({ onOpen }: ProjectListProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [briefs, setBriefs] = useState<Record<string, MorningBrief | null>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listProjects()
      .then(({ projects }) => {
        if (!cancelled) {
          setProjects(projects || []);
          (projects || []).forEach((p) => {
            getMorningBrief(p.id).then(({ brief }) => {
              if (!cancelled) setBriefs((prev) => ({ ...prev, [p.id]: brief }))
            }).catch(() => {})
          });
        }
      })
      .catch((err: unknown) => { if (!cancelled) setError(err instanceof Error ? err.message : "Unknown error"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true };
  }, []);

  if (loading) return <div className="automata-loading" role="status"><span className="automata-spinner" aria-hidden="true" /><p>Loading projects…</p></div>;
  if (error) return <div className="automata-error" role="alert"><p>{error}</p></div>;
  if (projects.length === 0) return <div className="automata-empty"><h2>No projects yet</h2><p>Register a project to start capturing memory.</p></div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {projects.map((p) => {
        const brief = briefs[p.id] || null;
        return (
          <button
            key={p.id}
            id={`project-card-${p.id}`}
            onClick={() => onOpen(p.id)}
            style={{
              width: '100%',
              textAlign: 'left',
              padding: '0.9rem 1rem',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border-soft)',
              background: 'transparent',
              color: 'var(--color-text-primary)',
              cursor: 'pointer',
            }}
          >
            <div style={{ fontWeight: 600 }}>{p.name}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-tertiary)', marginTop: '0.2rem' }}>{p.repo_path}</div>
            {brief && (
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', marginTop: '0.35rem' }}>
                {(brief.commits_count || 0)} commits · last edited: {brief.last_edited_file || "unknown"}
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}
