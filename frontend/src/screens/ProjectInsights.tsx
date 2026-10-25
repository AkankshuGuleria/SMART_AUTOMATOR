/**
 * screens/ProjectInsights.tsx
 * Per-project deep analytics: completion %, commits over time, file edits, todo stats, repo health.
 */
import { useState, useEffect, useMemo } from 'react'
import { motion } from 'framer-motion'
import { defaultContainer, defaultItem } from '../components/ui/VariantHelpers'
const container = defaultContainer
const item = defaultItem
import {
  Gauge, Shield, TrendingUp,
  CheckCircle2, AlertTriangle, Circle, GitBranch,
} from 'lucide-react'
import GlassCard from '../components/ui/GlassCard'
import ProgressRing from '../components/ui/ProgressRing'
import { ATLineChart, ATBarChart, ATDonutChart } from '../components/ui/AnimatedChart'
import {
  listProjects,
  getProjectAnalytics,
  getLiveMetrics,
  getHealth,
  getDecisions,
  type HealthStatus,
  type AnalyticsData,
  type Project,
  type DecisionEntry,
  type LiveMetrics,
} from '../lib/api'
import { usePolling } from '../lib/usePolling'

interface ProjectInsightsProps {
  projectId?: string
}

export default function ProjectInsights({ projectId: _projectId }: ProjectInsightsProps) {
  const [project] = useState<Project | null>(null)
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null)
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [liveMetrics, setLiveMetrics] = useState<LiveMetrics | null>(null)
  const [decisions, setDecisions] = useState<DecisionEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingDecisions, setLoadingDecisions] = useState(true)
  const [errorDecisions, setErrorDecisions] = useState<string | null>(null)
  const [resolvedProjectId, setResolvedProjectId] = useState<string | null>(null)

  const projectId = _projectId || resolvedProjectId

  // Resolve projectId from listProjects if not provided
  useEffect(() => {
    if (_projectId) {
      setResolvedProjectId(_projectId)
      return
    }
    let cancelled = false
    listProjects().then(({ projects }) => {
      if (!cancelled && projects.length > 0) {
        setResolvedProjectId(projects[0].id)
      }
    }).catch(() => {})
    return () => { cancelled = true }
  }, [_projectId])

  // Polling pauses while the window is hidden (usePolling). Health is already
  // tracked by App, so this screen only refreshes project data.
  usePolling(async () => {
    if (!projectId) return
    try {
      const { analytics } = await getProjectAnalytics(projectId)
      setAnalytics(analytics)
    } finally {
      setLoading(false)
    }
  }, 30000, [projectId], !!projectId)

  usePolling(async () => {
    setHealth(await getHealth())
  }, 30000)

  usePolling(async () => {
    if (projectId) setLiveMetrics(await getLiveMetrics(projectId))
  }, 15000, [projectId], !!projectId)

  usePolling(async () => {
    if (!projectId) return
    try {
      const { decisions } = await getDecisions(projectId, 10)
      setDecisions(decisions)
      setErrorDecisions(null)
    } catch (err) {
      setErrorDecisions(err instanceof Error ? err.message : 'Failed to load decisions')
    } finally {
      setLoadingDecisions(false)
    }
  }, 30000, [projectId], !!projectId)

  const completionPct = useMemo(() => {
    if (!analytics) return 0
    const { total, completed } = analytics.todo_stats
    if (total <= 0) return 0
    return Math.round((completed / total) * 100)
  }, [analytics])

  const tasksRemaining = analytics?.todo_stats.pending || 0

  const commitsTotal = analytics?.commits_over_time?.reduce((sum, c) => sum + c.count, 0) || 0
  const editsTotal = analytics?.file_edits_over_time?.reduce((sum, c) => sum + c.count, 0) || 0
  const sessionCount = analytics?.session_stats?.total_sessions || 0

  const aiConfidence = useMemo(() => {
    if (!health) return 0
    let score = 0
    if (health.api === 'ok') score += 25
    if (health.db?.db === 'connected') score += 25
    if (health.bedrock === 'configured') score += 25
    if (health.embedding === 'configured') score += 25
    return score
  }, [health])

  const openDecisions = decisions.length
  const memoryHealth = liveMetrics
    ? Math.round(Math.min(100, 40 + liveMetrics.memory.events_last_hour * 5 + liveMetrics.memory.decisions * 2))
    : (health?.db?.db === 'connected' ? 70 : 0)

  const completionDonut = useMemo(() => {
    const completed = analytics?.todo_stats.completed || 0
    const pending = analytics?.todo_stats.pending || 0
    return [
      { name: 'Done', value: completed, color: 'var(--accent)' },
      { name: 'Pending', value: pending, color: 'var(--border-hard)' },
    ]
  }, [analytics])

  const featureProgress = useMemo(() => {
    const embeddingOk = health?.embedding === 'configured'
    const bedrockOk = health?.bedrock === 'configured'

    return [
      { name: 'Memory Engine',     pct: Math.min(95, 40 + commitsTotal * 5 + editsTotal * 2), color: '#10b981' },
      { name: 'Vector Search',     pct: embeddingOk ? 88 : 0, color: '#22d3ee' },
      { name: 'Reasoning Engine',  pct: bedrockOk ? 72 : 0, color: '#a78bfa' },
      { name: 'Automation Layer',  pct: Math.min(90, 20 + sessionCount * 15), color: '#f59e0b' },
      { name: 'UI / Dashboard',    pct: Math.min(80, 20 + (analytics?.top_files?.length || 0) * 10 + editsTotal * 2), color: '#6c4fff' },
      { name: 'TODO Tracking',     pct: analytics?.todo_stats.total ? Math.round((analytics.todo_stats.completed / analytics.todo_stats.total) * 100) : 0, color: '#ec4899' },
      { name: 'Decision Engine',   pct: 10, color: '#6b7280' },
    ]
  }, [health, analytics, commitsTotal, editsTotal, sessionCount])

  const repoHealth = useMemo(() => {
    if (!health) return []
    return [
      { label: 'Backend API', ok: health.api === 'ok' },
      { label: 'CockroachDB', ok: health.db?.db === 'connected', value: health.db?.db === 'connected' ? 'Connected' : (health.db?.reason || 'Disconnected') },
      { label: 'Bedrock Configured', ok: health.bedrock === 'configured' },
      { label: 'Embeddings Configured', ok: health.embedding === 'configured' },
    ]
  }, [health])

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', stiffness: 220, damping: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <h1 style={{ marginBottom: '0.2rem' }}>Project Insights</h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
              {project ? project.name : 'Loading…'}
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
            value={loading ? 0 : completionPct}
            size={120}
            stroke={10}
            gradient={['var(--accent)', 'var(--ai-cyan)']}
            glow
            label={loading ? '—' : `${completionPct}%`}
            sublabel={loading ? '' : 'complete'}
          />
          <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>Overall Completion</span>
        </div>

        {/* Key metrics */}
        <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '1rem' }}>
          {[
            { label: 'Tasks Remaining', value: loading ? '—' : `${tasksRemaining}`, icon: Circle, color: 'var(--warning)' },
            { label: 'AI Confidence', value: loading ? '—' : `${aiConfidence}%`, icon: Gauge, color: 'var(--ai-cyan)' },
            { label: 'Open Decisions', value: loading ? '—' : `${openDecisions}`, icon: TrendingUp, color: 'var(--accent)' },
            { label: 'Memory Health', value: health ? `${memoryHealth}%` : '—', icon: Shield, color: memoryHealth > 0 ? 'var(--success)' : 'var(--warning)' },
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
        {/* Commits Over Time */}
        <motion.div variants={item}>
          <GlassCard hoverable>
            <ATLineChart
              title="Commits Over Time"
              data={analytics?.commits_over_time?.map(c => ({ day: c.day, count: c.count })) || []}
              lines={[
                { key: 'count', color: 'var(--accent)', label: 'Commits' },
              ]}
              xKey="day"
              height={180}
            />
          </GlassCard>
        </motion.div>

        {/* File Edits Over Time */}
        <motion.div variants={item}>
          <GlassCard hoverable>
            <ATBarChart
              title="File Edits Over Time"
              data={analytics?.file_edits_over_time?.map(c => ({ day: c.day, count: c.count })) || []}
              bars={[{ key: 'count', color: 'var(--ai-cyan)', label: 'Edits' }]}
              xKey="day"
              height={180}
            />
          </GlassCard>
        </motion.div>

        {/* Todo Breakdown */}
        <motion.div variants={item}>
          <GlassCard style={{ display: 'flex', justifyContent: 'center' }}>
            <ATDonutChart
              title="TODO Breakdown"
              data={completionDonut}
              size={160}
              label={loading ? '—' : `${completionPct}%`}
              sublabel={loading ? '' : 'done'}
            />
          </GlassCard>
        </motion.div>

        {/* Top Files */}
        <motion.div variants={item}>
          <GlassCard hoverable>
            <ATBarChart
              title="Most Edited Files"
              data={analytics?.top_files?.slice(0, 8).map(f => ({ file: f.file_path.split('/').pop() || f.file_path, count: f.edit_count })) || []}
              bars={[{ key: 'count', color: 'var(--warning)', label: 'Edits' }]}
              xKey="file"
              height={180}
              horizontal
            />
          </GlassCard>
        </motion.div>
      </motion.div>

      {/* Feature progress */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3, type: 'spring', stiffness: 200, damping: 24 }}>
        <GlassCard hoverable>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '1rem' }}>
            <TrendingUp size={15} color="var(--accent-2)" />
            <h3 style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Module Health</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            {featureProgress.map((f, i) => (
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

      {/* Recent Decisions */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35, type: 'spring', stiffness: 200, damping: 24 }}>
        <GlassCard hoverable>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.85rem' }}>
            <GitBranch size={15} color="var(--text-tertiary)" />
            <h3 style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Recent Decisions</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {loadingDecisions && (
              <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>
                Loading decisions…
              </div>
            )}
            {errorDecisions && (
              <div style={{ padding: '0.75rem', background: 'var(--error-muted)', borderRadius: 'var(--r-sm)', color: 'var(--error)', fontSize: '0.75rem' }}>
                {errorDecisions}
              </div>
            )}
            {!loadingDecisions && !errorDecisions && decisions.slice(0, 5).map((d, i) => (
              <div key={d.id || i} style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.6rem 0.75rem',
                background: 'var(--bg-elevated)',
                borderRadius: 'var(--r-sm)',
                border: '1px solid var(--border-soft)',
              }}>
                <div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-primary)', fontWeight: 500 }}>{d.decision}</div>
                  {d.rationale && <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', marginTop: 1 }}>{d.rationale.slice(0, 80)}</div>}
                </div>
                <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                  {d.decided_at ? new Date(d.decided_at).toLocaleDateString() : ''}
                </span>
              </div>
            ))}
            {!loadingDecisions && !errorDecisions && decisions.length === 0 && (
              <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>
                No decisions logged yet
              </div>
            )}
          </div>
        </GlassCard>
      </motion.div>

      {/* Repo health */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4, type: 'spring', stiffness: 200, damping: 24 }}>
        <GlassCard hoverable>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '1rem' }}>
            <Shield size={15} color="var(--text-tertiary)" />
            <h3 style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Repository Health</h3>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.5rem' }}>
            {repoHealth.map((r, i) => (
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
