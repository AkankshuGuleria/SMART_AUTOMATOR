/**
 * components/layout/FloatingSidebar.tsx
 * Collapsible floating sidebar with icon-only (collapsed) and text+icon (expanded) modes.
 * Spring-driven expand/collapse, AI status, workspace switcher, theme toggle.
 */
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, MessageSquare, Activity, Brain,
  Folder, Settings, ChevronRight,
  Cpu, Sun, Moon, RefreshCw, Zap, ListChecks, Inbox, ShieldCheck,
} from 'lucide-react'
import AIStatusBadge from '../ui/AIStatusBadge'
import type { Screen } from '../../lib/screens'

interface SidebarProps {
  activeScreen: Screen
  onNavigate: (screen: Screen) => void
  backendOnline: boolean
  theme: 'dark' | 'light'
  onThemeToggle: () => void
  reasoningMode?: string
  onModeChange?: (mode: string) => void
  expanded?: boolean
  onExpandedChange?: (expanded: boolean) => void
  /** Small count bubbles, e.g. { inbox: 3, tasks: 1 }. */
  badges?: Partial<Record<Screen, number>>
  /** Internet reachable (false = local model only). */
  aiOnline?: boolean
}

const NAV_ITEMS: { id: Screen; icon: React.FC<{ size?: number; strokeWidth?: number }>; label: string; section?: string }[] = [
  { id: 'dashboard',  icon: LayoutDashboard, label: 'Dashboard' },
  { id: 'chat',       icon: MessageSquare,   label: 'AI Chat' },
  { id: 'tasks',      icon: ListChecks,      label: 'Tasks' },
  { id: 'inbox',      icon: Inbox,           label: 'Needs from you' },
  { id: 'memory',     icon: Brain,           label: 'Memory' },
  { id: 'activity',   icon: Activity,        label: 'Activity' },
  { id: 'resources',  icon: Cpu,             label: 'Resources' },
  { id: 'projects',   icon: Folder,          label: 'Projects' },
  { id: 'restore',    icon: RefreshCw,       label: 'Restore' },
  { id: 'setup',      icon: ShieldCheck,     label: 'Setup & health' },
  { id: 'settings',   icon: Settings,        label: 'Settings' },
]

const SIDEBAR_W_CLOSED = 60
const SIDEBAR_W_OPEN   = 210

export default function FloatingSidebar({
  activeScreen,
  onNavigate,
  backendOnline,
  theme,
  onThemeToggle,
  reasoningMode = 'auto',
  onModeChange,
  expanded,
  onExpandedChange,
  badges = {},
  aiOnline = true,
}: SidebarProps) {
  const [localExpanded, setLocalExpanded] = useState(false)
  const isExpanded = expanded !== undefined ? expanded : localExpanded
  const setExpanded = (val: boolean) => {
    setLocalExpanded(val)
    onExpandedChange?.(val)
  }

  return (
    <motion.aside
      animate={{ width: isExpanded ? SIDEBAR_W_OPEN : SIDEBAR_W_CLOSED }}
      transition={{ type: 'spring', stiffness: 280, damping: 32, mass: 0.8 }}
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
      style={{
        position: 'fixed',
        left: 0, top: 0, bottom: 0,
        zIndex: 50,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        background: 'var(--bg-glass)',
        backdropFilter: 'var(--blur-lg)',
        WebkitBackdropFilter: 'var(--blur-lg)',
        borderRight: '1px solid var(--border-glass)',
        boxShadow: 'var(--shadow-xl)',
        paddingTop: 'env(safe-area-inset-top, 0)',
      }}
    >
      {/* Logo */}
      <div style={{
        height: 60,
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        borderBottom: '1px solid var(--border-soft)',
        flexShrink: 0,
        overflow: 'hidden',
        gap: 10,
      }}>
        {/* Logo mark */}
        <motion.div
          style={{
            width: 28, height: 28,
            borderRadius: 8,
            background: 'linear-gradient(135deg, var(--accent) 0%, var(--ai-cyan) 100%)',
            flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: 'var(--shadow-glow)',
          }}
          whileHover={{ scale: 1.08, rotate: 5 }}
          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
        >
          <Zap size={14} color="#fff" strokeWidth={2.5} />
        </motion.div>
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.15 }}
              style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
            >
              <span style={{
                fontFamily: 'var(--font-display)',
                fontWeight: 800,
                fontSize: '0.95rem',
                letterSpacing: '0.1em',
                background: 'linear-gradient(135deg, var(--accent-2) 0%, var(--ai-cyan) 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
                whiteSpace: 'nowrap',
              }}>AUTOMATA</span>
              <span style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', marginTop: -2 }}>v0.1 · AI OS</span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Status indicator */}
      <div style={{
        padding: '10px 16px',
        borderBottom: '1px solid var(--border-soft)',
        flexShrink: 0,
        overflow: 'hidden',
      }}>
        <AIStatusBadge
          state={backendOnline ? 'idle' : 'offline'}
          label={isExpanded ? (!backendOnline ? 'Agent offline' : aiOnline ? 'Online' : 'Offline · local AI') : undefined}
          size="sm"
        />
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, padding: '8px 0', overflow: 'auto', scrollbarWidth: 'none' }}>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          const isActive = activeScreen === item.id
          return (
            <motion.button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              whileHover={{ x: 2 }}
              whileTap={{ scale: 0.96 }}
              transition={{ type: 'spring', stiffness: 400, damping: 25 }}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '9px 16px',
                border: 'none',
                cursor: 'pointer',
                background: isActive ? 'var(--accent-muted)' : 'transparent',
                color: isActive ? 'var(--accent-2)' : 'var(--text-tertiary)',
                borderRight: isActive ? '2px solid var(--accent)' : '2px solid transparent',
                transition: 'color var(--dur-fast) var(--ease-in-out), background var(--dur-fast) var(--ease-in-out)',
                overflow: 'hidden',
              }}
            >
              <span style={{ position: 'relative', display: 'flex' }}>
                <Icon
                  size={18}
                  strokeWidth={isActive ? 2.2 : 1.8}
                />
                {(badges[item.id] ?? 0) > 0 && (
                  <span aria-label={`${badges[item.id]} pending`} style={{
                    position: 'absolute', top: -5, right: -7, minWidth: 14, height: 14, padding: '0 3px',
                    borderRadius: 7, background: 'var(--warning)', color: '#111', fontSize: '0.56rem',
                    fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>{badges[item.id]}</span>
                )}
              </span>
              <AnimatePresence>
                {isExpanded && (
                  <motion.span
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -6 }}
                    transition={{ duration: 0.14 }}
                    style={{
                      fontSize: '0.82rem',
                      fontWeight: isActive ? 600 : 400,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                    }}
                  >
                    {item.label}
                  </motion.span>
                )}
              </AnimatePresence>
            </motion.button>
          )
        })}
      </nav>

      {/* Bottom controls */}
      <div style={{
        padding: '8px 0',
        borderTop: '1px solid var(--border-soft)',
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
      }}>
        {/* Mode selector */}
        <AnimatePresence>
          {isExpanded && onModeChange && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              style={{ padding: '4px 12px 8px' }}
            >
              <select
                value={reasoningMode}
                onChange={e => onModeChange(e.target.value)}
                style={{
                  width: '100%',
                  padding: '5px 8px',
                  borderRadius: 'var(--r-sm)',
                  border: '1px solid var(--border-soft)',
                  background: 'var(--bg-elevated)',
                  color: 'var(--text-secondary)',
                  fontSize: '0.72rem',
                  fontFamily: 'var(--font-sans)',
                  cursor: 'pointer',
                  outline: 'none',
                }}
              >
                <option value="auto">Auto (Cloud → Local)</option>
                <option value="local">Local only</option>
                <option value="cloud">Cloud only</option>
              </select>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Theme toggle */}
        <motion.button
          onClick={onThemeToggle}
          whileTap={{ scale: 0.94 }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: '9px 16px',
            border: 'none',
            cursor: 'pointer',
            background: 'transparent',
            color: 'var(--text-tertiary)',
            width: '100%',
            overflow: 'hidden',
            transition: 'color var(--dur-fast) var(--ease-in-out)',
          }}
        >
          {theme === 'dark' ? <Sun size={18} strokeWidth={1.8} /> : <Moon size={18} strokeWidth={1.8} />}
          <AnimatePresence>
            {isExpanded && (
              <motion.span
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -6 }}
                transition={{ duration: 0.14 }}
                style={{ fontSize: '0.82rem', whiteSpace: 'nowrap' }}
              >
                {theme === 'dark' ? 'Light mode' : 'Dark mode'}
              </motion.span>
            )}
          </AnimatePresence>
        </motion.button>

        {/* Expand hint */}
        <AnimatePresence>
          {!isExpanded && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.3 }}
              exit={{ opacity: 0 }}
              style={{ display: 'flex', justifyContent: 'center', padding: '4px 0' }}
            >
              <ChevronRight size={12} color="var(--text-tertiary)" />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.aside>
  )
}
