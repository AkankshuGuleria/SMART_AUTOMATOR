/**
 * screens/ExplainRepository.tsx — AUTOMATA repository explanation screen
 *
 * Phase 4: Ground a structured repository explanation in README, folder
 * structure, and stored architecture notes via the explain-repository API.
 */

import React, { useState } from "react";
import { explainRepository, type ExplainRepositoryResult } from "../lib/api";

interface ExplainRepositoryProps {
  projectId?: string;
  repoPath: string;
}

export const ExplainRepositoryScreen: React.FC<ExplainRepositoryProps> = ({ projectId, repoPath }) => {
  const [result, setResult] = useState<ExplainRepositoryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const explain = async () => {
    if (!projectId || !repoPath) {
      setError("No project selected or repo path missing.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await explainRepository(projectId, repoPath);
      setResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="automata-explain-repo" aria-labelledby="explain-heading">
      <h1 id="explain-heading">Explain Repository</h1>
      <p className="explain-subtitle">Grounded in README, folder structure, and stored architecture notes.</p>

      <button id="explain-repo-btn" className="automata-btn-primary" onClick={explain} disabled={loading || !projectId || !repoPath}>
        Explain
      </button>

      {loading && (
        <div className="automata-loading" style={{ marginTop: "1.5rem" }}>
          <span className="automata-spinner" aria-label="Analyzing repository" />
          <p>Analyzing repository…</p>
        </div>
      )}

      {error && (
        <div className="automata-error" style={{ marginTop: "1.5rem" }} role="alert">
          <p>Could not explain repository: {error}</p>
          <p className="automata-error-hint">
            Ensure the AUTOMATA agent backend is running.
          </p>
        </div>
      )}

      {result && (
        <div style={{ marginTop: "1.5rem", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          <div className="explain-card">
            <h2>Explanation</h2>
            <p>{result.explanation ?? "No explanation generated."}</p>
          </div>

          <div className="explain-card">
            <h2>README Summary</h2>
            <p>{result.readme_summary ?? "No README found."}</p>
          </div>

          <div className="explain-card">
            <h2>Folder Structure</h2>
            {result.folder_structure.length === 0 && <p>No structure captured.</p>}
            <div className="explain-tree">
              {result.folder_structure
                .filter((entry) => entry.notable)
                .slice(0, 60)
                .map((entry, idx) => (
                  <div key={idx} className="explain-tree-row" style={{ padding: "0.2rem 0.4rem" }}>
                    <span style={{ color: "var(--color-accent)" }}>{entry.type === "dir" ? "📁" : "📄"}</span>
                    <code style={{ marginLeft: "0.5rem", fontSize: "0.8rem" }}>{entry.path}</code>
                  </div>
                ))}
            </div>
          </div>

          <div className="explain-card">
            <h2>Architecture Notes</h2>
            {result.architecture_notes.length === 0 && <p>No architecture notes stored yet.</p>}
            {result.architecture_notes.map((note, idx) => (
              <div key={idx} style={{ marginBottom: "0.75rem", padding: "0.75rem", background: "var(--color-bg-elevated)", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-soft)" }}>
                <strong style={{ color: "var(--color-text-primary)" }}>{note.title}</strong>
                <p style={{ marginTop: "0.35rem", fontSize: "0.875rem", color: "var(--color-text-secondary)" }}>{note.content}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
};

export default ExplainRepositoryScreen;
