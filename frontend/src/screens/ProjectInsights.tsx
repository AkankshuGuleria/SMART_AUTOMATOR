/**
 * screens/ProjectInsights.tsx
 * Per-project deep analytics: completion %, burndown, velocity, bugs, repo health, AI confidence.
 */
import { useState } from 'react'
import { motion } from 'framer-motion'
import { defaultContainer, defaultItem } from '../components/ui/VariantHelpers'
import {
  GitBranch, Bug, Gauge, Shield, TrendingUp,
  CheckCircle2, Circle, AlertTriangle,
} from 'lucide-react'
import GlassCard from '../components/ui/GlassCard'
import ProgressRing from '../components/ui/ProgressRing'
import { ATLineChart, ATBarChart, ATDonutChart } from '../components/ui/AnimatedChart'

// Mock project data
const PROJECTS = [
  { id: 'automata', name: 'AUTOMATA', completion: 62, confidence: 84, branch: 'main', prs: 0, staleBranches: 2 },
]

const BURNDOWN = Array.from({ length: 14 }, (_, i) => ({
  day: `D${i + 1}`,
  remaining: Math.max(0, 48 - i * 2.8 - Math.random() * 3),
  ideal: Math.max(0, 48 - i * 48 / 14),
}))

const VELOCITY = [
  { week: 'Wk 1', tasks: 6 }, { week: 'Wk 2', tasks: 9 }, { week: 'Wk 3', tasks: 7 },
  { week: 'Wk 4', tasks: 11 }, { week: 'Wk 5', tasks: 8 }, { week: 'Wk 6', tasks: 14 },
]

const BUGS = [
  { week: 'Wk 1', opened: 3, resolved: 2 }, { week: 'Wk 2', opened: 5, resolved: 4 },
  { week: 'Wk 3', opened: 2, resolved: 5 }, { week: 'Wk 4', opened: 4, resolved: 3 },
  { week: 'Wk 5', opened: 1, resolved: 4 }, { week: 'Wk 6', opened: 2, resolved: 2 },
]

const FEATURE_PROGRESS = [
  { name: 'Memory Engine',     pct: 95, color: '#10b981' },
  { name: 'Vector Search',     pct: 88, color: '#22d3ee' },
  { name: 'Reasoning Engine',  pct: 72, color: '#a78bfa' },
  { name: 'Automation Layer',  pct: 60, color: '#f59e0b' },
  { name: 'UI / Dashboard',    pct: 62, color: '#6c4fff' },
  { name: 'Restore Flow',      pct: 48, color: '#ec4899' },
  { name: 'Decision Engine',   pct: 10, color: '#6b7280' },
]

const REPO_HEALTH = [
  { label: 'Main branch protected', ok: true },
  { label: 'Pre-commit hooks enabled', ok: true },
  { label: 'Stale branches (>7d)', ok: false, value: '2 branches' },
  { label: 'Open pull requests', ok: true, value: '0 PRs' },
  { label: 'Test coverage', ok: false, value: 'Not configured' },
  { label: 'Secret baseline', ok: true },
]

const container = defaultContainer
const item = defaultItem

export default function ProjectInsights() {
  const [selectedProject] = useState(PROJECTS[0])

  const tasksRemaining = Math.round(BURNDOWN[BURNDOWN.length - 1].remaining)
  const completionDonut = [
    { name: 'Done', value: selectedProject.completion, color: 'var(--accent)' },
    { name: 'Remaining', value: 100 - selectedProject.completion, color: 'var(--border-hard)' },
  ]

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', stiffness: 220, damping: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <h1 style={{ marginBottom: '0.2rem' }}>Project Insights</h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
              {selectedProject.name} · <code style={{ fontSize: '0.78rem' }}>{selectedProject.branch}</code>
            </p>
          </div>
        </div>
      </motion.div>

      {/* ── Hero: Completion + Key Stats ─────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ type: 'spring', stiffness: 200, damping: 24 }}
        style={{
          background: 'linear-gradient(135deg, rgba(108,79,255,0.08) 0%, rgba(34,211,238,0.05) 100%)',
          border: '1px solid var(--border-glow)',
          borderRadius: 'var(--r-xl)',
          padding: '1.75rem 2rem',
          display: 'flex',
          alignItems: 'center',
          gap: '2.5rem',
          flexWrap: 'wrap',
        }}
      >
        {/* Completion ring */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
          <ProgressRing
            value={selectedProject.completion}
            size={120}
            stroke={10}
            gradient={['var(--accent)', 'var(--ai-cyan)']}
            glow
            label={`${selectedProject.completion}%`}
            sublabel="complete"
          />
          <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>Overall Completion</span>
        </div>

        {/* Key metrics */}
        <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '1rem' }}>
          {[
            { label: 'Tasks Remaining', value: `${tasksRemaining}`, icon: Circle, color: 'var(--warning)' },
            { label: 'AI Confidence', value: `${selectedProject.confidence}%`, icon: Gauge, color: 'var(--ai-cyan)' },
            { label: 'Open Bugs', value: '3', icon: Bug, color: 'var(--error)' },
            { label: 'Memory Health', value: '94%', icon: Shield, color: 'var(--success)' },
          ].map(stat => {
            const Icon = stat.icon
            return (
              <div key={stat.label} style={{
                display: 'flex', flexDirection: 'column', gap: '0.25rem',
                padding: '0.85rem 1rem',
                background: 'var(--bg-glass)',
                backdropFilter: 'var(--blur-sm)',
                borderRadius: 'var(--r-md)',
                border: '1px solid var(--border-glass)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <Icon size={13} color={stat.color} />
                  <span style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)' }}>{stat.label}</span>
                </div>
                <span style={{ fontSize: '1.4rem', fontWeight: 700, color: stat.color, fontFamily: 'var(--font-display)' }}>
                  {stat.value}
                </span>
              </div>
            )
          })}
        </div>
      </motion.div>

      {/* ── Charts grid ──────────────────────────────────────────────────── */}
      <motion.div variants={container} initial="hidden" animate="show" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        {/* Burndown */}
        <motion.div variants={item}>
          <GlassCard hoverable>
            <ATLineChart
              title="Burndown — Remaining vs Ideal"
              data={BURNDOWN.map(d => ({ ...d, remaining: Math.round(d.remaining), ideal: Math.round(d.ideal) }))}
              lines={[
                { key: 'remaining', color: 'var(--accent)', label: 'Remaining' },
                { key: 'ideal', color: 'rgba(100,116,139,0.5)', label: 'Ideal' },
              ]}
              xKey="day"
              height={180}
            />
          </GlassCard>
        </motion.div>

        {/* Velocity */}
        <motion.div variants={item}>
          <GlassCard hoverable>
            <ATBarChart
              title="Weekly Velocity (tasks completed)"
              data={VELOCITY}
              bars={[{ key: 'tasks', color: 'var(--ai-cyan)', label: 'Tasks' }]}
              xKey="week"
              height={180}
            />
          </GlassCard>
        </motion.div>

        {/* Bug trend */}
        <motion.div variants={item}>
          <GlassCard hoverable>
            <ATBarChart
              title="Bug Trend (opened vs resolved)"
              data={BUGS}
              bars={[
                { key: 'opened', color: 'var(--error)', label: 'Opened' },
                { key: 'resolved', color: 'var(--success)', label: 'Resolved' },
              ]}
              xKey="week"
              height={180}
            />
          </GlassCard>
        </motion.div>

        {/* Completion donut */}
        <motion.div variants={item}>
          <GlassCard style={{ display: 'flex', justifyContent: 'center' }}>
            <ATDonutChart
              title="Completion Breakdown"
              data={completionDonut}
              size={160}
              label={`${selectedProject.completion}%`}
              sublabel="done"
            />
          </GlassCard>
        </motion.div>
      </motion.div>

      {/* Feature progress */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3, type: 'spring', stiffness: 200, damping: 24 }}>
        <GlassCard hoverable>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '1rem' }}>
            <TrendingUp size={15} color="var(--accent-2)" />
            <h3 style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Feature Progress</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            {FEATURE_PROGRESS.map((f, i) => (
              <motion.div
                key={f.name}
                initial={{ opacity: 0, x: -16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 + i * 0.05, type: 'spring', stiffness: 300, damping: 26 }}
                style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}
              >
                <span style={{ width: 160, fontSize: '0.78rem', color: 'var(--text-secondary)', flexShrink: 0, whiteSpace: 'nowrap' }}>{f.name}</span>
                <div style={{ flex: 1, height: 6, background: 'var(--bg-elevated)', borderRadius: 99, overflow: 'hidden' }}>
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${f.pct}%` }}
                    transition={{ duration: 0.9, delay: 0.2 + i * 0.05, ease: [0.16, 1, 0.3, 1] }}
                    style={{ height: '100%', background: f.color, borderRadius: 99 }}
                  />
                </div>
                <span style={{ width: 36, fontSize: '0.72rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', textAlign: 'right' }}>{f.pct}%</span>
              </motion.div>
            ))}
          </div>
        </GlassCard>
      </motion.div>

      {/* Repo health */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4, type: 'spring', stiffness: 200, damping: 24 }}>
        <GlassCard hoverable>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '1rem' }}>
            <GitBranch size={15} color="var(--text-tertiary)" />
            <h3 style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Repository Health</h3>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.5rem' }}>
            {REPO_HEALTH.map((r, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.05 * i }}
                style={{
                  display: 'flex', alignItems: 'center', gap: '0.6rem',
                  padding: '0.55rem 0.75rem',
                  background: r.ok ? 'var(--success-muted)' : 'var(--error-muted)',
                  borderRadius: 'var(--r-sm)',
                  border: `1px solid ${r.ok ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}`,
                }}
              >
                {r.ok
                  ? <CheckCircle2 size={14} color="var(--success)" />
                  : <AlertTriangle size={14} color="var(--warning)" />
                }
                <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', flex: 1 }}>{r.label}</span>
                {r.value && <span style={{ fontSize: '0.68rem', color: r.ok ? 'var(--text-tertiary)' : 'var(--warning)', fontFamily: 'var(--font-mono)' }}>{r.value}</span>}
              </motion.div>
            ))}
          </div>
        </GlassCard>
      </motion.div>
    </div>
  )
}
