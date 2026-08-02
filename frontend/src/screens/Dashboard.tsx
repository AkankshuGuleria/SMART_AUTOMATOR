/**
 * screens/Dashboard.tsx
 * AUTOMATA premium dashboard — glass card grid, parallax hero, animated entrance.
 */
import { useState, useEffect, useRef } from 'react'
import { motion, useMotionValue, useSpring } from 'framer-motion'
import { defaultContainer, defaultItem } from '../components/ui/VariantHelpers'
import {
  Brain, GitCommit, CheckSquare, Zap, Clock,
  Activity, Terminal,
  FolderOpen, ChevronRight, Sparkles, Sun,
} from 'lucide-react'
import GlassCard from '../components/ui/GlassCard'
import ProgressRing from '../components/ui/ProgressRing'
import AIStatusBadge from '../components/ui/AIStatusBadge'
import { type HealthStatus } from '../lib/api'

interface DashboardProps {
  health: HealthStatus | null
  healthLoading: boolean
  projectId?: string
  onNavigate: (screen: string) => void
}

const HOUR = new Date().getHours()
const GREETING =
  HOUR < 12 ? 'Good morning' : HOUR < 17 ? 'Good afternoon' : 'Good evening'

const container = defaultContainer
const cardVariant = defaultItem

// Mock data — will be replaced with real API data
const MOCK_GIT = [
  { msg: 'feat: add vector retrieval pipeline', time: '2h ago', branch: 'main' },
  { msg: 'fix: handle null embeddings gracefully', time: '5h ago', branch: 'fix/embeddings' },
  { msg: 'chore: update bedrock client retry logic', time: '1d ago', branch: 'main' },
  { msg: 'feat: morning brief generation endpoint', time: '2d ago', branch: 'feat/brief' },
]
const MOCK_TASKS = [
  { text: 'Wire morning brief prompt template', done: false, priority: 'high' },
  { text: 'Complete workspace restore E2E test', done: false, priority: 'med' },
  { text: 'Dev server start/stop endpoints', done: false, priority: 'med' },
  { text: 'Browser launch URL configuration', done: true, priority: 'low' },
  { text: 'Connect CockroachDB', done: true, priority: 'low' },
]
const MOCK_SUGGESTIONS = [
  { label: '🔧 Complete Morning Brief', action: 'chat' },
  { label: '🧪 Run test suite', action: 'chat' },
  { label: '📊 View memory health', action: 'memory' },
]
const MOCK_SESSIONS = [
  { date: 'Today', duration: '2h 14m', commits: 3 },
  { date: 'Yesterday', duration: '4h 52m', commits: 7 },
  { date: 'Mon Aug 28', duration: '1h 33m', commits: 2 },
]

export default function Dashboard({ health, healthLoading, projectId: _projectId, onNavigate }: DashboardProps) {
  const [typed, setTyped] = useState('')
  const greeting = `${GREETING}, developer.`
  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)
  const springX = useSpring(mouseX, { stiffness: 60, damping: 25 })
  const springY = useSpring(mouseY, { stiffness: 60, damping: 25 })
  const heroRef = useRef<HTMLDivElement>(null)

  // Typewriter effect
  useEffect(() => {
    let i = 0
    const iv = setInterval(() => {
      if (i <= greeting.length) { setTyped(greeting.slice(0, i)); i++ }
      else clearInterval(iv)
    }, 38)
    return () => clearInterval(iv)
  }, [greeting])

  // Mouse parallax
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!heroRef.current) return
    const rect = heroRef.current.getBoundingClientRect()
    mouseX.set(((e.clientX - rect.left) / rect.width - 0.5) * 20)
    mouseY.set(((e.clientY - rect.top) / rect.height - 0.5) * 12)
  }

  const dbOk = health?.db?.db === 'connected'
  const apiOk = health?.api === 'ok'
  const memHealth = dbOk ? 94 : 0
  const tasksTotal = MOCK_TASKS.length
  const tasksDone  = MOCK_TASKS.filter(t => t.done).length

  return (
    <div
      style={{ flex: 1, overflowY: 'auto', padding: '1.5rem 1.5rem 2.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}
      onMouseMove={handleMouseMove}
      ref={heroRef}
    >
      {/* ── Hero greeting ────────────────────────────────────────────────── */}
      <motion.div
        style={{ position: 'relative', overflow: 'hidden' }}
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 200, damping: 24 }}
      >
        {/* Ambient blobs with parallax */}
        <motion.div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
          <motion.span style={{
            position: 'absolute', top: '-40%', right: '10%',
            width: 260, height: 260,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(108,79,255,0.12) 0%, transparent 70%)',
            x: springX,
            y: springY,
          }} />
          <motion.span style={{
            position: 'absolute', top: '10%', right: '40%',
            width: 180, height: 180,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(34,211,238,0.08) 0%, transparent 70%)',
            x: springX,
            y: springY,
          }} />
        </motion.div>

        <div style={{
          background: 'var(--bg-glass)',
          backdropFilter: 'var(--blur-md)',
          WebkitBackdropFilter: 'var(--blur-md)',
          border: '1px solid var(--border-glass)',
          borderRadius: 'var(--r-xl)',
          padding: '1.75rem 2rem',
          position: 'relative',
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
                <Sun size={16} color="var(--warning)" strokeWidth={2} />
                <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                  {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
                </span>
              </div>
              <h1 style={{ fontSize: 'clamp(1.4rem, 3vw, 2rem)', marginBottom: '0.5rem' }}>
                {typed}
                <motion.span
                  animate={{ opacity: [1, 0] }}
                  transition={{ duration: 0.6, repeat: Infinity, repeatType: 'reverse' }}
                  style={{ display: 'inline-block', width: 2, height: '1em', background: 'var(--accent)', marginLeft: 4, verticalAlign: 'text-bottom' }}
                />
              </h1>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)', maxWidth: 420 }}>
                Your AI memory engine has been running. Here's what you need to know.
              </p>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.5rem' }}>
              <AIStatusBadge state={apiOk ? 'idle' : 'offline'} label={apiOk ? 'Agent ready' : 'Agent offline'} size="md" />
              {healthLoading && <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>Connecting…</span>}
            </div>
          </div>
        </div>
      </motion.div>

      {/* ── Quick stats row ──────────────────────────────────────────────── */}
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.85rem' }}
      >
        {[
          { icon: Brain, label: 'Memory Health', value: `${memHealth}%`, color: 'var(--success)', ring: memHealth },
          { icon: GitCommit, label: 'Commits Today', value: '3', color: 'var(--info)', ring: 30 },
          { icon: CheckSquare, label: 'Tasks Done', value: `${tasksDone}/${tasksTotal}`, color: 'var(--accent-2)', ring: (tasksDone / tasksTotal) * 100 },
          { icon: Clock, label: 'Session Time', value: '2h 14m', color: 'var(--warning)', ring: 45 },
        ].map((stat) => {
          const Icon = stat.icon
          return (
            <motion.div key={stat.label} variants={cardVariant}>
              <GlassCard padding="1rem" hoverable>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.5rem' }}>
                      <Icon size={14} color={stat.color} strokeWidth={2} />
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', fontWeight: 500 }}>{stat.label}</span>
                    </div>
                    <span style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
                      {stat.value}
                    </span>
                  </div>
                  <ProgressRing value={stat.ring} size={46} stroke={4} color={stat.color} glow />
                </div>
              </GlassCard>
            </motion.div>
          )
        })}
      </motion.div>

      {/* ── Main content grid ────────────────────────────────────────────── */}
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 320px', gap: '1rem' }}
      >
        {/* Git Activity */}
        <motion.div variants={cardVariant}>
          <GlassCard hoverable style={{ height: '100%' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.85rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <GitCommit size={15} color="var(--info)" />
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>Git Activity</span>
              </div>
              <button onClick={() => onNavigate('activity')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', gap: 2 }}>
                <span style={{ fontSize: '0.65rem' }}>All</span><ChevronRight size={12} />
              </button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {MOCK_GIT.map((c, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.08, type: 'spring', stiffness: 300, damping: 28 }}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.15rem',
                    padding: '0.55rem 0.7rem',
                    background: 'var(--bg-elevated)',
                    borderRadius: 'var(--r-sm)',
                    border: '1px solid var(--border-soft)',
                  }}
                >
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', lineHeight: 1.3 }}>{c.msg}</span>
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>{c.time}</span>
                    <span style={{ fontSize: '0.62rem', background: 'var(--accent-muted)', color: 'var(--accent-2)', padding: '0 0.35rem', borderRadius: 3 }}>{c.branch}</span>
                  </div>
                </motion.div>
              ))}
            </div>
          </GlassCard>
        </motion.div>

        {/* Pending Tasks */}
        <motion.div variants={cardVariant}>
          <GlassCard hoverable style={{ height: '100%' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.85rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <CheckSquare size={15} color="var(--accent-2)" />
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>Pending Tasks</span>
              </div>
              <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                {tasksDone}/{tasksTotal} done
              </span>
            </div>
            {/* Progress bar */}
            <div style={{ height: 3, background: 'var(--bg-elevated)', borderRadius: 99, marginBottom: '0.85rem', overflow: 'hidden' }}>
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${(tasksDone / tasksTotal) * 100}%` }}
                transition={{ duration: 1, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
                style={{ height: '100%', background: 'linear-gradient(90deg, var(--accent) 0%, var(--ai-cyan) 100%)', borderRadius: 99 }}
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              {MOCK_TASKS.filter(t => !t.done).map((t, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.1 + i * 0.07, type: 'spring', stiffness: 300, damping: 28 }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.6rem',
                    padding: '0.45rem 0.6rem',
                    borderRadius: 'var(--r-sm)',
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border-soft)',
                  }}
                >
                  <span style={{
                    width: 16, height: 16, borderRadius: 4,
                    border: '1.5px solid',
                    borderColor: t.priority === 'high' ? 'var(--error)' : t.priority === 'med' ? 'var(--warning)' : 'var(--border-hard)',
                    flexShrink: 0,
                  }} />
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', flex: 1 }}>{t.text}</span>
                  <span style={{ fontSize: '0.6rem', color: t.priority === 'high' ? 'var(--error)' : t.priority === 'med' ? 'var(--warning)' : 'var(--text-tertiary)', fontWeight: 600 }}>
                    {t.priority}
                  </span>
                </motion.div>
              ))}
            </div>
          </GlassCard>
        </motion.div>

        {/* Right column: AI Suggestions + Sessions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* AI Suggestions */}
          <motion.div variants={cardVariant}>
            <GlassCard glowing>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.85rem' }}>
                <Sparkles size={15} color="var(--ai-cyan)" />
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>AI Suggestions</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {MOCK_SUGGESTIONS.map((s, i) => (
                  <motion.button
                    key={i}
                    onClick={() => onNavigate(s.action as string)}
                    whileHover={{ x: 4 }}
                    whileTap={{ scale: 0.97 }}
                    transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '0.55rem 0.7rem',
                      background: 'var(--ai-cyan-muted)',
                      border: '1px solid rgba(34,211,238,0.15)',
                      borderRadius: 'var(--r-sm)',
                      cursor: 'pointer',
                      color: 'var(--text-secondary)',
                      fontSize: '0.8rem',
                      textAlign: 'left',
                      width: '100%',
                    }}
                  >
                    <span>{s.label}</span>
                    <ChevronRight size={14} color="var(--ai-cyan)" />
                  </motion.button>
                ))}
              </div>
            </GlassCard>
          </motion.div>

          {/* Recent sessions */}
          <motion.div variants={cardVariant}>
            <GlassCard>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.85rem' }}>
                <Clock size={15} color="var(--text-tertiary)" />
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>Recent Sessions</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {MOCK_SESSIONS.map((s, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: i < MOCK_SESSIONS.length - 1 ? '1px solid var(--border-soft)' : 'none' }}>
                    <div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-primary)', fontWeight: 500 }}>{s.date}</div>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', marginTop: 1 }}>{s.commits} commits</div>
                    </div>
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{s.duration}</span>
                  </div>
                ))}
              </div>
            </GlassCard>
          </motion.div>
        </div>
      </motion.div>

      {/* ── System status row ────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, type: 'spring', stiffness: 200, damping: 24 }}
        style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}
      >
        {[
          { label: 'Backend API', ok: apiOk, icon: Zap },
          { label: 'CockroachDB', ok: dbOk, icon: Activity },
          { label: 'Memory Engine', ok: dbOk, icon: Brain },
          { label: 'Terminal', ok: true, icon: Terminal },
          { label: 'Projects', ok: true, icon: FolderOpen },
        ].map(({ label, ok, icon: Icon }) => (
          <div
            key={label}
            onClick={() => onNavigate('resources')}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.4rem',
              padding: '0.35rem 0.75rem',
              borderRadius: 'var(--r-full)',
              background: ok ? 'var(--success-muted)' : 'var(--error-muted)',
              border: `1px solid ${ok ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}`,
              cursor: 'pointer',
            }}
          >
            <Icon size={12} color={ok ? 'var(--success)' : 'var(--error)'} />
            <span style={{ fontSize: '0.7rem', color: ok ? 'var(--success)' : 'var(--error)', fontWeight: 500 }}>{label}</span>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: ok ? 'var(--success)' : 'var(--error)', marginLeft: 2 }} />
          </div>
        ))}
      </motion.div>
    </div>
  )
}
