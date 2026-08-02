/**
 * App.tsx — AUTOMATA root component v2.0 (immersive redesign)
 *
 * Layout:
 * - Floating sidebar (left, icon-only, expands on hover) — navigation + status
 * - Main content area with AnimatePresence screen transitions
 * - Command palette overlay (Ctrl+K)
 * - Ambient background layer
 *
 * Screens: Dashboard · AI Chat · Memory · Activity · Resources · Projects · Restore · Settings
 */

import { useState, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  getHealth,
  getReasoningMode,
  setReasoningMode as saveReasoningMode,
  type HealthStatus,
} from './lib/api'
import FloatingSidebar from './components/layout/FloatingSidebar'
import CommandPaletteV2 from './components/layout/CommandPaletteV2'

// Screens
import Dashboard from './screens/Dashboard'
import AIChatScreen from './screens/AIChatScreen'
import MemoryVisualization from './screens/MemoryVisualization'
import ResourceUsage from './screens/ResourceUsage'
import ProjectInsights from './screens/ProjectInsights'
import WorkspaceRestoreScreen from './screens/WorkspaceRestoreScreen'
import SettingsScreen from './screens/SettingsScreen'

// Legacy screens (still functional, kept for backward compat)
import ActivityFeed from './components/ActivityFeed'
import ProjectList from './components/ProjectList'

type Screen = 'dashboard' | 'chat' | 'activity' | 'resources' | 'projects' | 'memory' | 'restore' | 'settings'
type Theme = 'dark' | 'light'

const DEMO_PROJECT_ID = '2efec7e0-92db-4591-9594-026ff8399a3c'

const pageVariants = {
  initial:  { opacity: 0, y: 12, filter: 'blur(4px)' },
  animate:  { opacity: 1, y: 0, filter: 'blur(0px)', transition: { type: 'spring' as const, stiffness: 220, damping: 26 } },
  exit:     { opacity: 0, y: -8, filter: 'blur(2px)', transition: { duration: 0.18, ease: [0.4, 0, 1, 1] as [number, number, number, number] } },
}

export default function App() {
  const [screen, setScreen] = useState<Screen>('dashboard')
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [healthLoading, setHealthLoading] = useState(true)
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null)
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false)
  const [sidebarExpanded, setSidebarExpanded] = useState(false)
  const [reasoningMode, setReasoningMode] = useState<string>('auto')
  const [theme, setTheme] = useState<Theme>('dark')

  // Apply theme to document root
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const handleModeChange = async (newMode: string) => {
    try {
      await saveReasoningMode(newMode)
      setReasoningMode(newMode)
    } catch { /* ignore */ }
  }

  // Health polling
  useEffect(() => {
    let cancelled = false
    const check = () => {
      getHealth()
        .then(h => { if (!cancelled) { setHealth(h); setHealthLoading(false) } })
        .catch(() => { if (!cancelled) { setHealth(null); setHealthLoading(false) } })
    }
    check()
    const id = setInterval(check, 30_000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  // Load reasoning mode
  useEffect(() => {
    getReasoningMode()
      .then((s: { reasoning_mode: string }) => setReasoningMode(s.reasoning_mode))
      .catch(() => {})
  }, [])

  // Keyboard shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setCmdPaletteOpen(v => !v)
      }
      if (e.key === 'Escape') setCmdPaletteOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const backendOnline = health?.api === 'ok'

  const handleNavigate = (s: Screen) => {
    setScreen(s)
  }

  return (
    <div style={{ display: 'flex', width: '100%', height: '100dvh', overflow: 'hidden', position: 'relative', background: 'var(--bg-base)' }}>

      {/* ── Ambient background ──────────────────────────────────────────── */}
      <div className="ambient-bg" />

      {/* ── Floating Sidebar ────────────────────────────────────────────── */}
      <FloatingSidebar
        activeScreen={screen}
        onNavigate={handleNavigate}
        backendOnline={backendOnline}
        theme={theme}
        onThemeToggle={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
        reasoningMode={reasoningMode}
        onModeChange={handleModeChange}
        expanded={sidebarExpanded}
        onExpandedChange={setSidebarExpanded}
      />

      {/* ── Main content ─────────────────────────────────────────────────── */}
      <main style={{
        flex: 1,
        marginLeft: sidebarExpanded ? 210 : 60,
        transition: 'margin-left var(--dur-base) var(--ease-in-out)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        position: 'relative',
        zIndex: 1,
      }}>
        {/* Backend offline banner */}
        <AnimatePresence>
          {!healthLoading && !backendOnline && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 300, damping: 28 }}
              style={{ overflow: 'hidden' }}
            >
              <div style={{
                background: 'var(--error-muted)',
                borderBottom: '1px solid rgba(239,68,68,0.25)',
                padding: '0.5rem 1.25rem',
                fontSize: '0.78rem',
                color: 'var(--error)',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}>
                <span>⚠</span>
                <span>Backend offline. Start it:</span>
                <code style={{ fontSize: '0.72rem', background: 'rgba(239,68,68,0.12)', padding: '0.1rem 0.5rem', borderRadius: 4 }}>
                  cd backend &amp;&amp; uv run python main.py
                </code>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Screen content with transitions */}
        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <AnimatePresence mode="wait">
            {screen === 'dashboard' && (
              <motion.div key="dashboard" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }} {...pageVariants}>
                <Dashboard
                  health={health}
                  healthLoading={healthLoading}
                  projectId={activeProjectId || DEMO_PROJECT_ID}
                  onNavigate={handleNavigate as (s: string) => void}
                />
              </motion.div>
            )}

            {screen === 'chat' && (
              <motion.div key="chat" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }} {...pageVariants}>
                <AIChatScreen
                  projectId={activeProjectId || DEMO_PROJECT_ID}
                />
              </motion.div>
            )}

            {screen === 'memory' && (
              <motion.div key="memory" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }} {...pageVariants}>
                <MemoryVisualization />
              </motion.div>
            )}

            {screen === 'activity' && (
              <motion.div key="activity" style={{ flex: 1, overflow: 'auto', padding: '1.5rem' }} {...pageVariants}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
                  <h1>Activity Feed</h1>
                  {activeProjectId && (
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                      {activeProjectId.slice(0, 8)}…
                    </span>
                  )}
                </div>
                <ActivityFeed
                  projectId={activeProjectId || DEMO_PROJECT_ID}
                  onClearBadge={() => {}}
                />
              </motion.div>
            )}

            {screen === 'resources' && (
              <motion.div key="resources" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }} {...pageVariants}>
                <ResourceUsage />
              </motion.div>
            )}

            {screen === 'projects' && (
              <motion.div key="projects" style={{ flex: 1, overflow: 'auto', padding: '1.5rem' }} {...pageVariants}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                  <h1>Projects</h1>
                  {activeProjectId && (
                    <button
                      onClick={() => setActiveProjectId(null)}
                      style={{
                        padding: '0.4rem 0.85rem',
                        borderRadius: 'var(--r-sm)',
                        border: '1px solid var(--border-soft)',
                        background: 'var(--bg-elevated)',
                        color: 'var(--text-secondary)',
                        fontSize: '0.78rem',
                        cursor: 'pointer',
                      }}
                    >
                      ← Back to Project List
                    </button>
                  )}
                </div>
                {activeProjectId ? (
                  <ProjectInsights />
                ) : (
                  <ProjectList onOpen={id => { setActiveProjectId(id); setScreen('chat') }} />
                )}
              </motion.div>
            )}

            {screen === 'restore' && (
              <motion.div key="restore" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }} {...pageVariants}>
                <WorkspaceRestoreScreen />
              </motion.div>
            )}

            {screen === 'settings' && (
              <motion.div key="settings" style={{ flex: 1, overflow: 'auto', display: 'flex', justifyContent: 'center' }} {...pageVariants}>
                <SettingsScreen
                  reasoningMode={reasoningMode}
                  onModeChange={handleModeChange}
                  theme={theme}
                  onThemeToggle={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Ctrl+K hint floating pill */}
        <AnimatePresence>
          {!cmdPaletteOpen && (
            <motion.button
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              transition={{ type: 'spring', stiffness: 300, damping: 28 }}
              onClick={() => setCmdPaletteOpen(true)}
              style={{
                position: 'fixed',
                bottom: 20,
                right: 20,
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '0.45rem 0.9rem',
                borderRadius: 'var(--r-full)',
                border: '1px solid var(--border-soft)',
                background: 'var(--bg-glass)',
                backdropFilter: 'var(--blur-md)',
                WebkitBackdropFilter: 'var(--blur-md)',
                color: 'var(--text-tertiary)',
                fontSize: '0.72rem',
                cursor: 'pointer',
                fontFamily: 'var(--font-sans)',
                zIndex: 40,
                boxShadow: 'var(--shadow-md)',
              }}
            >
              <kbd style={{ fontSize: '0.62rem' }}>⌘K</kbd>
              <span>Command</span>
            </motion.button>
          )}
        </AnimatePresence>
      </main>

      {/* ── Command Palette ──────────────────────────────────────────────── */}
      <AnimatePresence>
        {cmdPaletteOpen && (
          <CommandPaletteV2
            onClose={() => setCmdPaletteOpen(false)}
            onNavigate={(s: Screen) => { handleNavigate(s); setCmdPaletteOpen(false) }}
            projectId={activeProjectId || DEMO_PROJECT_ID}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
