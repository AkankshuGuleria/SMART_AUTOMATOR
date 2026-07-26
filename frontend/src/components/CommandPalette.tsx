/**
 * components/CommandPalette.tsx — Cmd/Ctrl+K fallback actions.
 */

import { useState, useEffect } from "react";

interface CommandPaletteProps {
  projectId: string;
  onClose: () => void;
  onNavigate: (projectId: string) => void;
}

const COMMANDS = [
  { id: 'resume', label: 'Resume workspace', projectId: '' },
  { id: 'brief', label: 'Open morning brief', projectId: '' },
  { id: 'activity', label: 'Open activity feed', projectId: '' },
  { id: 'projects', label: 'Show all projects', projectId: '' },
  { id: 'tests', label: 'Run tests', projectId: '' },
  { id: 'explain', label: 'Explain repository', projectId: '' },
];

export default function CommandPalette({ projectId, onClose, onNavigate }: CommandPaletteProps) {
  const [query, setQuery] = useState("");

  useEffect(() => {
    const first = COMMANDS[0];
    onNavigate(first.projectId || projectId);
  }, []);

  const filtered = COMMANDS.filter((c) => c.label.toLowerCase().includes(query.toLowerCase()));

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: '15vh', zIndex: 9999 }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: '520px', maxHeight: '50vh', background: 'var(--color-bg-surface)', border: '1px solid var(--color-border-soft)', borderRadius: 'var(--radius-md)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <input
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Type a command…"
          style={{ padding: '0.75rem 1rem', border: 'none', borderBottom: '1px solid var(--color-border-soft)', background: 'transparent', color: 'var(--color-text-primary)', fontSize: '1rem', outline: 'none' }}
        />
        <div style={{ overflow: 'auto', padding: '0.5rem' }}>
          {filtered.map((c) => (
            <button
              key={c.id}
              onClick={() => {
                if (c.id === 'resume') onNavigate(projectId);
                else if (c.id === 'brief') {
                  // handled by nav state in App; for now navigate and rely on App nav
                  onNavigate(projectId);
                }
                else onNavigate(c.projectId || projectId);
                onClose();
              }}
              style={{
                width: '100%',
                textAlign: 'left',
                padding: '0.6rem 0.75rem',
                borderRadius: 'var(--radius-md)',
                border: 'none',
                background: 'transparent',
                color: 'var(--color-text-primary)',
                cursor: 'pointer',
              }}
            >
              {c.label}
            </button>
          ))}
          {filtered.length === 0 && <p style={{ padding: '0.75rem', opacity: 0.7 }}>No matches</p>}
        </div>
      </div>
    </div>
  );
}
