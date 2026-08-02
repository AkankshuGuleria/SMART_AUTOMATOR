/**
 * components/layout/CommandPaletteV2.tsx
 * Glass overlay command palette: fuzzy search, keyboard nav, grouped results.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  Search, LayoutDashboard, MessageSquare, Brain,
  Activity, Cpu, Folder, RefreshCw, Settings,
  ArrowRight, Command,
} from 'lucide-react'

type Screen = 'dashboard' | 'chat' | 'activity' | 'resources' | 'projects' | 'memory' | 'restore' | 'settings'

interface Command {
  id: string
  label: string
  description?: string
  screen?: Screen
  action?: () => void
  icon: React.FC<{ size?: number }>
  group: string
  keywords?: string[]
}

interface CommandPaletteProps {
  onClose: () => void
  onNavigate: (screen: Screen) => void
  projectId?: string
  onChatMessage?: (msg: string) => void
}

const SCREEN_COMMANDS: Command[] = [
  { id: 'nav-dashboard',  label: 'Go to Dashboard',         group: 'Navigate', icon: LayoutDashboard, screen: 'dashboard', keywords: ['home', 'overview'] },
  { id: 'nav-chat',       label: 'Go to AI Chat',           group: 'Navigate', icon: MessageSquare,   screen: 'chat',      keywords: ['ask', 'agent', 'query'] },
  { id: 'nav-memory',     label: 'Open Memory Visualization', group: 'Navigate', icon: Brain,          screen: 'memory',    keywords: ['graph', 'knowledge'] },
  { id: 'nav-activity',   label: 'View Activity Feed',      group: 'Navigate', icon: Activity,        screen: 'activity',  keywords: ['feed', 'events'] },
  { id: 'nav-resources',  label: 'Resources & Usage',       group: 'Navigate', icon: Cpu,             screen: 'resources', keywords: ['cpu', 'ram', 'time', 'usage'] },
  { id: 'nav-projects',   label: 'Projects',                group: 'Navigate', icon: Folder,          screen: 'projects',  keywords: ['repo', 'workspace'] },
  { id: 'nav-restore',    label: 'Restore Workspace',       group: 'Navigate', icon: RefreshCw,       screen: 'restore',   keywords: ['recover', 'session'] },
  { id: 'nav-settings',   label: 'Settings',                group: 'Navigate', icon: Settings,        screen: 'settings',  keywords: ['config', 'preferences'] },
]

function fuzzyScore(query: string, target: string, keywords?: string[]): number {
  const q = query.toLowerCase()
  const t = target.toLowerCase()
  if (t.startsWith(q)) return 100
  if (t.includes(q)) return 70
  if (keywords?.some(k => k.includes(q))) return 50
  let score = 0
  let ti = 0
  for (let qi = 0; qi < q.length; qi++) {
    while (ti < t.length && t[ti] !== q[qi]) ti++
    if (ti < t.length) { score += 1; ti++ }
    else return 0
  }
  return score * 10
}

export default function CommandPaletteV2({ onClose, onNavigate, onChatMessage }: CommandPaletteProps) {
  const [query, setQuery] = useState('')
  const [selectedIdx, setSelectedIdx] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const allCommands = [...SCREEN_COMMANDS]
  if (onChatMessage && query.trim() && query.trim().length > 2) {
    allCommands.push({
      id: 'ask-ai',
      label: `Ask AI: "${query.trim()}"`,
      group: 'AI',
      icon: MessageSquare,
      action: () => { onChatMessage(query.trim()); onNavigate('chat'); onClose() },
      keywords: [],
    })
  }

  const filtered = query.trim()
    ? allCommands
        .map(c => ({ cmd: c, score: fuzzyScore(query, c.label, c.keywords) }))
        .filter(x => x.score > 0)
        .sort((a, b) => b.score - a.score)
        .map(x => x.cmd)
    : allCommands

  const groups: Record<string, Command[]> = {}
  for (const c of filtered) {
    if (!groups[c.group]) groups[c.group] = []
    groups[c.group].push(c)
  }

  const flatList = filtered

  const execute = useCallback((cmd: Command) => {
    if (cmd.action) { cmd.action(); return }
    if (cmd.screen) onNavigate(cmd.screen)
    onClose()
  }, [onNavigate, onClose])

  useEffect(() => {
    setSelectedIdx(0)
  }, [query])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') { e.preventDefault(); setSelectedIdx(i => Math.min(i + 1, flatList.length - 1)) }
      if (e.key === 'ArrowUp')   { e.preventDefault(); setSelectedIdx(i => Math.max(i - 1, 0)) }
      if (e.key === 'Enter' && flatList[selectedIdx]) execute(flatList[selectedIdx])
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [flatList, selectedIdx, execute, onClose])

  // Scroll active item into view
  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-idx="${selectedIdx}"]`)
    el?.scrollIntoView({ block: 'nearest' })
  }, [selectedIdx])

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.15 }}
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0,
        background: 'var(--bg-overlay)',
        backdropFilter: 'var(--blur-sm)',
        WebkitBackdropFilter: 'var(--blur-sm)',
        zIndex: 200,
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '18vh',
      }}
    >
      <motion.div
        initial={{ opacity: 0, y: -20, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -12, scale: 0.97 }}
        transition={{ type: 'spring', stiffness: 380, damping: 32 }}
        onClick={e => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: 560,
          margin: '0 1rem',
          background: 'var(--bg-frosted)',
          backdropFilter: 'var(--blur-xl)',
          WebkitBackdropFilter: 'var(--blur-xl)',
          border: '1px solid var(--border-soft)',
          borderRadius: 'var(--r-xl)',
          boxShadow: 'var(--shadow-xl), 0 0 60px rgba(108,79,255,0.12)',
          overflow: 'hidden',
        }}
      >
        {/* Search input */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
          padding: '1rem 1.25rem',
          borderBottom: '1px solid var(--border-soft)',
        }}>
          <Search size={18} color="var(--text-tertiary)" strokeWidth={2} />
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search commands, screens, ask AI…"
            style={{
              flex: 1,
              background: 'none',
              border: 'none',
              outline: 'none',
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-sans)',
              fontSize: '0.95rem',
            }}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Command size={12} color="var(--text-tertiary)" />
            <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>K</span>
          </div>
        </div>

        {/* Results */}
        <div ref={listRef} style={{ maxHeight: 360, overflow: 'auto', padding: '0.5rem' }}>
          {Object.entries(groups).map(([group, cmds]) => (
            <div key={group}>
              <div style={{ padding: '0.4rem 0.75rem', fontSize: '0.65rem', color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                {group}
              </div>
              {cmds.map(cmd => {
                const idx = flatList.indexOf(cmd)
                const Icon = cmd.icon
                const isSelected = idx === selectedIdx
                return (
                  <motion.button
                    key={cmd.id}
                    data-idx={idx}
                    onClick={() => execute(cmd)}
                    onMouseEnter={() => setSelectedIdx(idx)}
                    whileTap={{ scale: 0.98 }}
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.75rem',
                      padding: '0.6rem 0.75rem',
                      border: 'none',
                      background: isSelected ? 'var(--accent-muted)' : 'transparent',
                      borderRadius: 'var(--r-md)',
                      cursor: 'pointer',
                      color: isSelected ? 'var(--accent-2)' : 'var(--text-secondary)',
                      transition: 'background var(--dur-fast) var(--ease-in-out), color var(--dur-fast) var(--ease-in-out)',
                      textAlign: 'left',
                    }}
                  >
                    <Icon size={16} />
                    <span style={{ flex: 1, fontSize: '0.85rem', fontWeight: isSelected ? 500 : 400 }}>{cmd.label}</span>
                    {isSelected && <ArrowRight size={14} style={{ flexShrink: 0 }} />}
                  </motion.button>
                )
              })}
            </div>
          ))}
          {filtered.length === 0 && (
            <div style={{ padding: '2rem 1rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
              No results for "{query}"
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '0.6rem 1.25rem',
          borderTop: '1px solid var(--border-soft)',
          display: 'flex',
          gap: '1rem',
          fontSize: '0.65rem',
          color: 'var(--text-tertiary)',
        }}>
          {[['↑↓', 'navigate'], ['↵', 'select'], ['esc', 'close']].map(([k, l]) => (
            <span key={k} style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
              <kbd style={{ fontSize: '0.6rem' }}>{k}</kbd> {l}
            </span>
          ))}
        </div>
      </motion.div>
    </motion.div>
  )
}
