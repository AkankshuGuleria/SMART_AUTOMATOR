/**
 * App.tsx — AUTOMATA root component (chat-first redesign).
 *
 * Product shape:
 * - Left: live project cards
 * - Center: persistent chat as primary interface
 * - Right: conversation thread with action cards + tool status
 * - Command palette: Cmd/Ctrl+K
 */

import { useState, useEffect } from 'react'
import { getHealth, type HealthStatus } from './lib/api'
import ProjectList from './components/ProjectList'
import ChatPanel from './components/ChatPanel'
import ActivityFeed from './components/ActivityFeed'
import MorningBriefWrapper from './components/MorningBriefWrapper'
import CommandPalette from './components/CommandPalette'

type Screen = 'chat' | 'projects' | 'activity' | 'brief'

const DEMO_PROJECT_ID = '2efec7e0-92db-4591-9594-026ff8399a3c'

export default function App() {
  const [screen, setScreen] = useState<Screen>('chat')
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [healthLoading, setHealthLoading] = useState(true)
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null)
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false)
  const [activityBadge, setActivityBadge] = useState(0)

  useEffect(() => {
    let cancelled = false
    getHealth()
      .then((h) => { if (!cancelled) setHealth(h) })
      .catch(() => { if (!cancelled) setHealth(null) })
      .finally(() => { if (!cancelled) setHealthLoading(false) })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setCmdPaletteOpen((v) => !v)
      }
      if (e.key === 'Escape') {
        setCmdPaletteOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const dbConnected = health?.db?.db === 'connected'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100dvh' }}>
      <header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0.6rem 1.25rem',
        background: 'var(--color-bg-surface)',
        borderBottom: '1px solid var(--color-border-soft)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '1rem', fontWeight: 700, letterSpacing: '0.08em', color: 'var(--color-accent)' }}>AUTOMATA</span>
          <span style={{ fontSize: '0.7rem', color: 'var(--color-text-tertiary)' }}>v0.1.0</span>
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: healthLoading ? 'var(--color-warning)' : dbConnected ? 'var(--color-success)' : 'var(--color-error)', display: 'inline-block' }} />
          <span style={{ color: 'var(--color-text-tertiary)', fontSize: '0.75rem' }}>
            {healthLoading ? 'Connecting…' : dbConnected ? 'Memory connected' : 'Memory offline'}
          </span>
        </div>

        <nav style={{ display: 'flex', gap: '0.25rem' }} aria-label="Primary">
          {([
            ['chat', 'Chat'],
            ['projects', 'Projects'],
            ['activity', `Activity${activityBadge ? ` (${activityBadge})` : ''}`],
            ['brief', 'Brief'],
          ] as [Screen, string][]).map(([id, label]) => (
            <button
              key={id}
              id={`nav-${id}`}
              onClick={() => setScreen(id)}
              aria-current={screen === id ? 'page' : undefined}
              style={{
                padding: '0.45rem 0.9rem',
                borderRadius: 'var(--radius-md)',
                border: 'none',
                background: screen === id ? 'var(--color-accent-muted)' : 'transparent',
                color: screen === id ? 'var(--color-accent-hover)' : 'var(--color-text-secondary)',
                fontFamily: 'inherit',
                fontSize: '0.8rem',
                fontWeight: screen === id ? 600 : 400,
                cursor: 'pointer',
              }}
            >
              {label}
            </button>
          ))}
        </nav>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            id="cmd-palette-btn"
            onClick={() => setCmdPaletteOpen(true)}
            style={{
              padding: '0.35rem 0.7rem',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border-soft)',
              background: 'transparent',
              color: 'var(--color-text-secondary)',
              fontSize: '0.7rem',
              cursor: 'pointer',
            }}
          >
            ⌘K
          </button>
        </div>
      </header>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {screen === 'projects' && (
          <aside style={{
            width: '320px',
            borderRight: '1px solid var(--color-border-soft)',
            background: 'var(--color-bg-surface)',
            overflow: 'auto',
            padding: '1rem',
          }}>
            <ProjectList onOpen={(id) => { setActiveProjectId(id); setScreen('chat') }} />
          </aside>
        )}

        <main style={{ flex: 1, overflow: 'auto' }}>
          {screen === 'chat' && (
            <section aria-labelledby="chat-heading" style={{ height: '100%' }}>
              <h1 id="chat-heading" className="visually-hidden">Agent chat</h1>
              <ChatPanel projectId={activeProjectId || DEMO_PROJECT_ID} onActivity={() => setActivityBadge((v) => v + 1)} onOpenProject={(id) => { setActiveProjectId(id); setScreen('projects') }} cmdPaletteOpen={cmdPaletteOpen} onCloseCmdPalette={() => setCmdPaletteOpen(false)} />
            </section>
          )}

          {screen === 'projects' && (
            <section aria-labelledby="projects-heading" style={{ padding: '1rem' }}>
              <h1 id="projects-heading" style={{ marginBottom: '1rem' }}>Your projects</h1>
              <ProjectList onOpen={(id) => { setActiveProjectId(id); setScreen('chat') }} />
            </section>
          )}

          {screen === 'activity' && (
            <section aria-labelledby="activity-heading" style={{ padding: '1rem' }}>
              <h1 id="activity-heading" style={{ marginBottom: '1rem' }}>Activity feed</h1>
              <ActivityFeed projectId={activeProjectId || DEMO_PROJECT_ID} onClearBadge={() => setActivityBadge(0)} />
            </section>
          )}

          {screen === 'brief' && (
            <section aria-labelledby="brief-heading" style={{ padding: '1rem' }}>
              <h1 id="brief-heading" style={{ marginBottom: '1rem' }}>Morning Brief</h1>
              <MorningBriefWrapper projectId={activeProjectId || DEMO_PROJECT_ID} />
            </section>
          )}
        </main>

        {cmdPaletteOpen && (
          <CommandPalette
            projectId={activeProjectId || DEMO_PROJECT_ID}
            onClose={() => setCmdPaletteOpen(false)}
            onNavigate={(id) => {
              setActiveProjectId(id)
              setScreen('chat')
              setCmdPaletteOpen(false)
            }}
          />
        )}
      </div>
    </div>
  )
}
