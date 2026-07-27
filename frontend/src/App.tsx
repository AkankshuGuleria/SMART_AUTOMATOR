/**
 * App.tsx — AUTOMATA root component (chat-first redesign).
 *
 * Layout:
 * - Top: header nav with AUTOMATA branding + status + screen switcher + ⌘K
 * - Main: full-height screen content (chat / projects / activity / brief)
 * - Overlay: command palette (Ctrl+K)
 */

import { useState, useEffect } from 'react'
import { getHealth, setReasoningMode, type HealthStatus } from './lib/api'
import ProjectList from './components/ProjectList'
import ChatPanel from './components/ChatPanel'
import ActivityFeed from './components/ActivityFeed'
import MorningBriefWrapper from './components/MorningBriefWrapper'
import CommandPalette from './components/CommandPalette'

type Screen = 'chat' | 'projects' | 'activity' | 'brief'

const DEMO_PROJECT_ID = '2efec7e0-92db-4591-9594-026ff8399a3c'

const NAV_ITEMS: [Screen, string, string][] = [
  ['chat',     '💬', 'Chat'],
  ['projects', '📁', 'Projects'],
  ['activity', '⚡', 'Activity'],
  ['brief',    '🌅', 'Brief'],
]

export default function App() {
  const [screen, setScreen] = useState<Screen>('chat')
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [healthLoading, setHealthLoading] = useState(true)
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null)
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false)
  const [activityBadge, setActivityBadge] = useState(0)
  const [reasoningMode, setReasoningMode] = useState<string>('auto')
  const [modeLoading, setModeLoading] = useState(false)

  const handleModeChange = async (newMode: string) => {
    setModeLoading(true)
    try {
      await setReasoningMode(newMode)
      setReasoningMode(newMode)
    } catch {
      // ignore
    } finally {
      setModeLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    const check = () => {
      getHealth()
        .then((h) => { if (!cancelled) { setHealth(h); setHealthLoading(false) } })
        .catch(() => { if (!cancelled) { setHealth(null); setHealthLoading(false) } })
    }
    check()
    // Re-check every 30 s
    const id = setInterval(check, 30_000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  // Load current reasoning mode
  useEffect(() => {
    getReasoningMode()
      .then((s) => setReasoningMode(s.reasoning_mode))
      .catch(() => {})
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
  const backendOnline = health?.api === 'ok'
  const statusText = healthLoading
    ? 'Connecting…'
    : backendOnline
      ? dbConnected ? 'Memory connected' : 'Backend online · DB offline'
      : 'Backend offline'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100dvh', overflow: 'hidden' }}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 1.25rem',
        height: 48,
        background: 'var(--color-bg-surface)',
        borderBottom: '1px solid var(--color-border-soft)',
        flexShrink: 0,
        backdropFilter: 'blur(12px)',
        zIndex: 10,
      }}>
        {/* Logo + status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', minWidth: 0 }}>
          <span style={{
            fontSize: '0.95rem',
            fontWeight: 800,
            letterSpacing: '0.12em',
            background: 'linear-gradient(135deg, #9a7dff, #7c5af4)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            userSelect: 'none',
          }}>AUTOMATA</span>
          <span style={{ fontSize: '0.65rem', color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-mono)' }}>v0.1.0</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span className={`status-dot ${healthLoading ? 'loading' : backendOnline && dbConnected ? 'online' : 'offline'}`} />
            <span style={{ color: 'var(--color-text-tertiary)', fontSize: '0.72rem' }}>{statusText}</span>
          </div>
        </div>

        {/* Navigation */}
        <nav style={{ display: 'flex', gap: '0.15rem' }} aria-label="Primary">
          {NAV_ITEMS.map(([id, icon, label]) => {
            const isActive = screen === id
            const badge = id === 'activity' && activityBadge > 0 ? activityBadge : 0
            return (
              <button
                key={id}
                id={`nav-${id}`}
                onClick={() => { setScreen(id); if (id === 'activity') setActivityBadge(0) }}
                aria-current={isActive ? 'page' : undefined}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  padding: '0.35rem 0.75rem',
                  borderRadius: 'var(--radius-md)',
                  border: isActive ? '1px solid var(--color-border-glow)' : '1px solid transparent',
                  background: isActive ? 'var(--color-accent-muted)' : 'transparent',
                  color: isActive ? 'var(--color-accent-hover)' : 'var(--color-text-secondary)',
                  fontFamily: 'var(--font-sans)',
                  fontSize: '0.78rem',
                  fontWeight: isActive ? 600 : 400,
                  cursor: 'pointer',
                  transition: 'all var(--transition-fast)',
                  position: 'relative',
                }}
              >
                <span>{icon}</span>
                <span>{label}</span>
                {badge > 0 && (
                  <span style={{
                    position: 'absolute',
                    top: -4, right: -4,
                    width: 16, height: 16,
                    borderRadius: '50%',
                    background: 'var(--color-error)',
                    color: '#fff',
                    fontSize: '0.55rem',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontWeight: 700,
                  }}>{badge}</span>
                )}
              </button>
            )
          })}
        </nav>

        {/* Cmd palette trigger */}
        <button
          id="cmd-palette-btn"
          className="btn-ghost"
          onClick={() => setCmdPaletteOpen(true)}
          style={{
            padding: '0.3rem 0.65rem',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border-soft)',
            background: 'transparent',
            color: 'var(--color-text-secondary)',
            fontSize: '0.72rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.3rem',
            fontFamily: 'var(--font-sans)',
          }}
        >
          <kbd style={{ fontSize: '0.65rem' }}>⌘K</kbd>
        </button>

        {/* Backend mode selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <span style={{ fontSize: '0.65rem', color: 'var(--color-text-tertiary)' }}>⚙</span>
          <select
            id="backend-mode-select"
            value={reasoningMode}
            onChange={(e) => handleModeChange(e.target.value)}
            disabled={modeLoading}
            style={{
              padding: '0.25rem 0.5rem',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border-soft)',
              background: 'var(--color-bg-elevated)',
              color: 'var(--color-text-primary)',
              fontSize: '0.7rem',
              fontFamily: 'var(--font-sans)',
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            <option value="auto">Auto (Ollama → Cloud)</option>
            <option value="local">Local (Ollama only)</option>
            <option value="cloud">Cloud (Bedrock + APIs)</option>
          </select>
        </div>
      </header>

      {/* ── Backend offline banner ───────────────────────────────────────── */}
      {!healthLoading && !backendOnline && (
        <div style={{
          background: 'var(--color-error-muted)',
          borderBottom: '1px solid rgba(248,113,113,0.3)',
          padding: '0.5rem 1.25rem',
          fontSize: '0.78rem',
          color: 'var(--color-error)',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          flexShrink: 0,
        }}>
          <span>⚠</span>
          <span>Backend is offline. Start it with:</span>
          <code style={{ fontSize: '0.72rem', background: 'rgba(248,113,113,0.15)', padding: '0.1rem 0.4rem', borderRadius: 4, border: 'none' }}>
            cd backend &amp;&amp; python main.py
          </code>
        </div>
      )}

      {/* ── Main content ─────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', position: 'relative' }}>
        {/* Projects sidebar (visible alongside main area) */}
        {screen === 'projects' && (
          <aside style={{
            width: 300,
            borderRight: '1px solid var(--color-border-soft)',
            background: 'var(--color-bg-surface)',
            overflow: 'auto',
            padding: '1rem',
            flexShrink: 0,
          }}>
            <ProjectList onOpen={(id) => { setActiveProjectId(id); setScreen('chat') }} />
          </aside>
        )}

        <main style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
          {screen === 'chat' && (
            <section aria-labelledby="chat-heading" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <h1 id="chat-heading" className="visually-hidden">Agent chat</h1>
              <ChatPanel
                projectId={activeProjectId || DEMO_PROJECT_ID}
                onActivity={() => setActivityBadge((v) => v + 1)}
                onOpenProject={(id) => { setActiveProjectId(id); setScreen('projects') }}
                cmdPaletteOpen={cmdPaletteOpen}
                onCloseCmdPalette={() => setCmdPaletteOpen(false)}
              />
            </section>
          )}

          {screen === 'projects' && (
            <section aria-labelledby="projects-heading" style={{ padding: '1.25rem' }}>
              <h1 id="projects-heading" style={{ marginBottom: '1rem' }}>Your projects</h1>
              <ProjectList onOpen={(id) => { setActiveProjectId(id); setScreen('chat') }} />
            </section>
          )}

          {screen === 'activity' && (
            <section aria-labelledby="activity-heading" style={{ padding: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                <h1 id="activity-heading">Activity feed</h1>
                {activeProjectId && (
                  <span style={{ fontSize: '0.72rem', color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                    {activeProjectId.slice(0, 8)}…
                  </span>
                )}
              </div>
              <ActivityFeed
                projectId={activeProjectId || DEMO_PROJECT_ID}
                onClearBadge={() => setActivityBadge(0)}
              />
            </section>
          )}

          {screen === 'brief' && (
            <section aria-labelledby="brief-heading" style={{ padding: '1.25rem' }}>
              <h1 id="brief-heading" style={{ marginBottom: '1rem' }}>Morning Brief</h1>
              <MorningBriefWrapper projectId={activeProjectId || DEMO_PROJECT_ID} />
            </section>
          )}
        </main>

        {/* Command palette overlay */}
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
