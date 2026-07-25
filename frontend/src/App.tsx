/**
 * App.tsx — AUTOMATA root component
 *
 * Phase 0: Simple tab-based navigation between the three screens.
 *          No router library yet — add React Router before Phase 3 if needed.
 * Phase 1+: Wire active project selection from CockroachDB.
 */

import { useState, useEffect } from 'react'
import { MorningBriefScreen } from './screens/MorningBrief'
import { RestoreWorkspaceScreen } from './screens/RestoreWorkspace'
import { QueryChatScreen } from './screens/QueryChat'
import { getHealth, type HealthStatus } from './lib/api'

type Screen = 'brief' | 'restore' | 'query'

// Phase 0 demo project ID — replace with real project selection in Phase 1.
const DEMO_PROJECT_ID = '0f90c2f9-0d9a-4787-ab07-8d4699fb4b13'

export default function App() {
  const [screen, setScreen] = useState<Screen>('brief')
  const [health, setHealth] = useState<HealthStatus | null>(null)

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
  }, [])

  const navItems: { id: Screen; label: string }[] = [
    { id: 'brief',   label: 'Morning Brief' },
    { id: 'restore', label: 'Restore Workspace' },
    { id: 'query',   label: 'Memory Query' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0.75rem 1.5rem',
        background: 'var(--color-bg-surface)',
        borderBottom: '1px solid var(--color-border-soft)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{
            fontSize: '1rem',
            fontWeight: 700,
            letterSpacing: '0.08em',
            color: 'var(--color-accent)',
          }}>AUTOMATA</span>
          <span style={{ fontSize: '0.7rem', color: 'var(--color-text-tertiary)' }}>v0.1.0</span>
        </div>

        {/* Connection status indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem' }}>
          <span style={{
            width: '6px', height: '6px',
            borderRadius: '50%',
            background: health?.db?.db === 'connected'
              ? 'var(--color-success)'
              : health === null
                ? 'var(--color-warning)'
                : 'var(--color-error)',
            display: 'inline-block',
          }} />
          <span style={{ color: 'var(--color-text-tertiary)' }}>
            {health === null
              ? 'Connecting…'
              : health.db?.db === 'connected'
                ? 'Memory connected'
                : 'Memory offline'}
          </span>
        </div>
      </header>

      {/* ── Nav ────────────────────────────────────────────────────────────── */}
      <nav style={{
        display: 'flex',
        gap: '0.25rem',
        padding: '0.5rem 1.5rem',
        background: 'var(--color-bg-surface)',
        borderBottom: '1px solid var(--color-border-soft)',
      }}
        aria-label="Main navigation"
      >
        {navItems.map(({ id, label }) => (
          <button
            key={id}
            id={`nav-${id}`}
            onClick={() => setScreen(id)}
            aria-current={screen === id ? 'page' : undefined}
            style={{
              padding: '0.375rem 0.875rem',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              background: screen === id ? 'var(--color-accent-muted)' : 'transparent',
              color: screen === id ? 'var(--color-accent-hover)' : 'var(--color-text-secondary)',
              fontFamily: 'inherit',
              fontSize: '0.8rem',
              fontWeight: screen === id ? 600 : 400,
              cursor: 'pointer',
              transition: 'background var(--transition-fast), color var(--transition-fast)',
            }}
          >
            {label}
          </button>
        ))}
      </nav>

      {/* ── Screen ─────────────────────────────────────────────────────────── */}
      <main style={{ flex: 1, overflow: 'auto', padding: '1rem' }}>
        {screen === 'brief'   && <MorningBriefScreen    projectId={DEMO_PROJECT_ID} />}
        {screen === 'restore' && <RestoreWorkspaceScreen projectId={DEMO_PROJECT_ID} />}
        {screen === 'query'   && <QueryChatScreen        projectId={DEMO_PROJECT_ID} />}
      </main>
    </div>
  )
}
