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
  KeyRound, FlaskConical, TrendingUp, Shield,
  CheckCircle2, AlertTriangle, Circle, GitBranch,
} from 'lucide-react'
import GlassCard from '../components/ui/GlassCard'
import ProgressRing from '../components/ui/ProgressRing'
import { ATLineChart, ATBarChart, ATDonutChart } from '../components/ui/AnimatedChart'
import {
  listProjects,
  getProjectAnalytics,
  getDecisions,
  getProjectProfile,
  type AnalyticsData,
  type DecisionEntry,
  type ProjectProfile,
} from '../lib/api'
import { usePolling } from '../lib/usePolling'
import ProjectProfileCard from '../components/ProjectProfileCard'

interface ProjectInsightsProps {
  projectId?: string
}

export default function ProjectInsights({ projectId: _projectId }: ProjectInsightsProps) {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null)
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

  const [profile, setProfile] = useState<ProjectProfile | null>(null)
  usePolling(async () => {
    if (projectId) setProfile(await getProjectProfile(projectId))
  }, 120000, [projectId], !!projectId)
  const envVars = profile?.env.variables ?? []
  const envMissing = envVars.filter(v => !v.set)

  const completionPct = useMemo(() => {
    if (!analytics) return 0
    const { total, completed } = analytics.todo_stats
    if (total <= 0) return 0
    return Math.round((completed / total) * 100)
  }, [analytics])
  // With no tracked tasks, show readiness from this project's own modules instead of a fake 0%.
  const hasTasks = (analytics?.todo_stats.total ?? 0) > 0
  const modules = profile?.modules ?? []
  const readiness = modules.length ? Math.round(modules.reduce((s, m) => s + m.pct, 0) / modules.length) : null
  const ringValue = hasTasks ? completionPct : readiness ?? 0
  const ringLabel = hasTasks ? `${completionPct}%` : readiness === null ? '—' : `${readiness}%`
  const ringSub = hasTasks ? 'tasks done' : 'ready'
  const ringCaption = hasTasks ? 'Task completion' : 'Readiness (avg. of modules)'

  const tasksRemaining = analytics?.todo_stats.pending || 0


  const openDecisions = decisions.length
  const completionDonut = useMemo(() => {
    const completed = analytics?.todo_stats.completed || 0
    const pending = analytics?.todo_stats.pending || 0
    return [
      { name: 'Done', value: completed, color: 'var(--accent)' },
      { name: 'Pending', value: pending, color: 'var(--border-hard)' },
    ]
  }, [analytics])

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', stiffness: 220, damping: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <h1 style={{ marginBottom: '0.2rem' }}>Project Insights</h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
              Detected from this project's files and captured activity.
            </p>
          </div>
        </div>
      </motion.div>

      <ProjectProfileCard projectId={projectId ?? undefined} />

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
            value={loading ? 0 : ringValue}
            size={120}
            stroke={10}
            gradient={['var(--accent)', 'var(--ai-cyan)']}
            glow
            label={loading ? '—' : ringLabel}
            sublabel={loading ? '' : ringSub}
          />
          <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{ringCaption}</span>
        </div>

        {/* Key metrics */}
        <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '1rem' }}>
          {[
            { label: 'Tasks Remaining', value: loading ? '—' : `${tasksRemaining}`, icon: Circle, color: 'var(--warning)' },
            { label: 'Env vars to set', value: profile ? `${envMissing.length}` : '—', icon: KeyRound, color: envMissing.length ? 'var(--warning)' : 'var(--success)' },
            { label: 'Open Decisions', value: loading ? '—' : `${openDecisions}`, icon: TrendingUp, color: 'var(--accent)' },
            { label: 'Test files', value: profile ? `${profile.tests.files}` : '—', icon: FlaskConical, color: profile?.tests.files ? 'var(--success)' : 'var(--warning)' },
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
              label={loading ? '—' : hasTasks ? `${completionPct}%` : '—'}
              sublabel={loading ? '' : hasTasks ? 'done' : 'no TODOs'}
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

      {/* Requirements detected from this project's files */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4, type: 'spring', stiffness: 200, damping: 24 }}>
        <GlassCard hoverable>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '1rem' }}>
            <Shield size={15} color="var(--text-tertiary)" />
            <h3 style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Requirements</h3>
            <span style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)' }}>environment variables this project uses</span>
          </div>
          {!profile && <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>Reading the project…</div>}
          {profile && envVars.length === 0 && (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
              This {profile.type?.label.toLowerCase() ?? 'project'} does not use any environment variables.
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '0.5rem' }}>
            {envVars.map(v => (
              <div key={v.name} title={v.used_in ? `Used in ${v.used_in}` : v.declared_in ? `Declared in ${v.declared_in}` : ''} style={{
                display: 'flex', alignItems: 'center', gap: '0.6rem', padding: '0.55rem 0.75rem',
                background: v.set ? 'var(--success-muted)' : 'var(--warning-muted)', borderRadius: 'var(--r-sm)',
                border: `1px solid ${v.set ? 'rgba(16,185,129,0.2)' : 'rgba(245,158,11,0.25)'}`,
              }}>
                {v.set ? <CheckCircle2 size={14} color="var(--success)" /> : <AlertTriangle size={14} color="var(--warning)" />}
                <span style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', flex: 1, fontFamily: 'var(--font-mono)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{v.name}</span>
                <span style={{ fontSize: '0.66rem', color: 'var(--text-tertiary)' }}>{v.provider ?? v.kind.replace('_', ' ')}</span>
              </div>
            ))}
          </div>
        </GlassCard>
      </motion.div>
    </div>
  )
}
