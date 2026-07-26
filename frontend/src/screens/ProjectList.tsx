/**
 * screens/ProjectList.tsx — AUTOMATA project selection screen.
 *
 * Owns: listing tracked projects and opening a project context view.
 * Never: talks to CockroachDB or Bedrock directly.
 */

import { useState, useEffect } from "react";
import { listProjects, type Project } from "../lib/api";

interface ProjectListProps {
  onOpen: (projectId: string) => void;
  onOpenBrief: () => void;
}

export default function ProjectList({ onOpen, onOpenBrief }: ProjectListProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listProjects()
      .then(({ projects }) => {
        if (!cancelled) setProjects(projects || []);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unknown error");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true };
  }, []);

  if (loading) {
    return (
      <div className="automata-loading" role="status" aria-live="polite">
        <span className="automata-spinner" aria-hidden="true" />
        <p>Loading projects…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="automata-error" role="alert">
        <p>Could not load projects</p>
        <p>{error}</p>
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div className="automata-empty">
        <h2>No projects yet</h2>
        <p>Register a project to start capturing memory.</p>
        <p className="automata-phase-note">Use the API or wait for capture to detect your workspace.</p>
      </div>
    );
  }

  return (
    <div>
      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        {projects.map((p) => (
          <li key={p.id}>
            <button
              id={`project-${p.id}`}
              onClick={() => onOpen(p.id)}
              style={{
                width: "100%",
                textAlign: "left",
                padding: "0.85rem 1rem",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--color-border-soft)",
                background: "transparent",
                color: "var(--color-text-primary)",
                cursor: "pointer",
              }}
            >
              <div style={{ fontWeight: 600 }}>{p.name}</div>
              <div style={{ fontSize: "0.75rem", color: "var(--color-text-tertiary)", marginTop: "0.25rem" }}>
                {p.repo_path}
              </div>
            </button>
          </li>
        ))}
      </ul>

      <div style={{ marginTop: "1.25rem" }}>
        <button
          id="open-morning-brief-btn"
          onClick={onOpenBrief}
          style={{
            padding: "0.5rem 0.75rem",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--color-border-soft)",
            background: "transparent",
            color: "var(--color-text-secondary)",
            cursor: "pointer",
          }}
        >
          Open Morning Brief
        </button>
      </div>
    </div>
  );
}
