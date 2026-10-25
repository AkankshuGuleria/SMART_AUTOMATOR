/**
 * screens/Dashboard.tsx
 * AUTOMATA developer command center — dynamic, project-driven dashboard.
 */
import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { motion, useMotionValue, useSpring } from 'framer-motion'
import { defaultContainer, defaultItem } from '../components/ui/VariantHelpers'
import {
  Brain, GitCommit, CheckSquare, Zap, Clock,
  Activity, Terminal, FolderOpen, ChevronRight, Sparkles, Sun,
  RefreshCw, Play, Folder, Plus, Check, Loader2,
  Cpu, HardDrive, MemoryStick, GitBranch, Monitor, RotateCcw, FileCode,
} from 'lucide-react'
import GlassCard from '../components/ui/GlassCard'
import ProgressRing from '../components/ui/ProgressRing'
import AIStatusBadge from '../components/ui/AIStatusBadge'
import {
  type HealthStatus,
  getProjectAnalytics,
  getActivityFeed,
  getMorningBrief,
  generateMorningBrief,
  getTodos,
  updateTodoStatus,
  getSessions,
  getGitBranch,
  getLiveMetrics,
  getSystemMetrics,
  getUsageSummary,
  type AnalyticsData,
  type SystemMetrics,
  type UsageSummary,
  type ActivityItem,
  type MorningBrief,
  type Todo,
  type Session,
  type Project,
  type LiveMetrics,
} from '../lib/api'
import { usePolling } from '../lib/usePolling'

interface DashboardProps {
  health: HealthStatus | null
  healthLoading: boolean
  projectId?: string
  projects: Project[]
  projectsLoading: boolean
  onProjectChange?: (id: string) => void
  onNavigate: (screen: string) => void
}

function formatRelativeTime(dateStr: string): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function formatDuration(seconds: number): string {
  if (seconds <= 0) return '0m'
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  if (hours > 0) return `${hours}h ${mins}m`
  return `${mins}m`
}

function getGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

const container = defaultContainer
const cardVariant = defaultItem

export default function Dashboard({ health, healthLoading, projectId: _projectId, projects, projectsLoading, onProjectChange, onNavigate }: DashboardProps) {
  const projectId = _projectId ?? null
  const currentProject = useMemo(() => projects.find(p => p.id === projectId) ?? null, [projects, projectId])

  const [branch, setBranch] = useState<string | null>(null)
  const [branchError, setBranchError] = useState<string | null>(null)
  const [branchLoading, setBranchLoading] = useState(false)

  // Activity
  const [activityItems, setActivityItems] = useState<ActivityItem[]>([])
  const [loadingActivity, setLoadingActivity] = useState(true)
  const [errorActivity, setErrorActivity] = useState<string | null>(null)

  // Analytics
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null)
  const [loadingAnalytics, setLoadingAnalytics] = useState(true)

  // Brief
  const [brief, setBrief] = useState<MorningBrief | null>(null)
  const [loadingBrief, setLoadingBrief] = useState(true)
  const [regenerating, setRegenerating] = useState(false)
  const [briefError, setBriefError] = useState<string | null>(null)

  // Todos
  const [todos, setTodos] = useState<Todo[]>([])
  const [loadingTodos, setLoadingTodos] = useState(true)
  const [errorTodos, setErrorTodos] = useState<string | null>(null)
  const [togglingTodo, setTogglingTodo] = useState<string | null>(null)

  // Sessions
  const [sessions, setSessions] = useState<Session[]>([])
  const [loadingSessions, setLoadingSessions] = useState(true)

  // Live agent metrics, host resources, today's app usage
  const [liveMetrics, setLiveMetrics] = useState<LiveMetrics | null>(null)
  const [system, setSystem] = useState<SystemMetrics | null>(null)
  const [usage, setUsage] = useState<UsageSummary | null>(null)

  // Project selector
  const [selectorOpen, setSelectorOpen] = useState(false)
  const selectorRef = useRef<HTMLDivElement>(null)

  // Typewriter
  const [typed, setTyped] = useState('')
  const greeting = `${getGreeting()}, developer.`

  // Parallax
  const heroRef = useRef<HTMLDivElement>(null)
  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)
  const springX = useSpring(mouseX, { stiffness: 60, damping: 25 })
  const springY = useSpring(mouseY, { stiffness: 60, damping: 25 })

  // Fetch branch
  useEffect(() => {
    if (!projectId) return
    let cancelled = false
    setBranchLoading(true)
    setBranchError(null)
    getGitBranch(projectId).then(({ branch, error }) => {
      if (!cancelled) {
        setBranch(branch)
        setBranchError(error)
        setBranchLoading(false)
      }
    }).catch((err) => {
      if (!cancelled) {
        setBranchError(err instanceof Error ? err.message : 'Failed to load branch')
        setBranchLoading(false)
      }
    })
    return () => { cancelled = true }
  }, [projectId])

  // Fetch activity
  useEffect(() => {
    if (!projectId) return
    let cancelled = false
    setLoadingActivity(true)
    setErrorActivity(null)
    getActivityFeed(projectId, 10).then(({ items }) => {
      if (!cancelled) {
        setActivityItems(items)
        setLoadingActivity(false)
      }
    }).catch((err) => {
      if (!cancelled) {
        setErrorActivity(err instanceof Error ? err.message : 'Failed to load activity')
        setLoadingActivity(false)
      }
    })
    return () => { cancelled = true }
  }, [projectId])

  // Fetch analytics
  useEffect(() => {
    if (!projectId) return
    let cancelled = false
    setLoadingAnalytics(true)
    getProjectAnalytics(projectId).then(({ analytics }) => {
      if (!cancelled) {
        setAnalytics(analytics)
        setLoadingAnalytics(false)
      }
    }).catch(() => {
      if (!cancelled) setLoadingAnalytics(false)
    })
    return () => { cancelled = true }
  }, [projectId])

  // Fetch brief (auto-generate)
  useEffect(() => {
    if (!projectId) return
    let cancelled = false
    setLoadingBrief(true)
    setBrief(null)
    getMorningBrief(projectId).then(({ brief }) => {
      if (cancelled) return
      if (brief) {
        setBrief(brief)
        setLoadingBrief(false)
        return
      }
      return generateMorningBrief(projectId).then(({ success, brief: generated }) => {
        if (cancelled) return
        if (success && generated) setBrief(generated)
      }).catch(() => {}).finally(() => {
        if (!cancelled) setLoadingBrief(false)
      })
    }).catch(() => {
      if (!cancelled) setLoadingBrief(false)
    })
    return () => { cancelled = true }
  }, [projectId])

  const handleRegenerateBrief = useCallback(async () => {
    if (!projectId) return
    setRegenerating(true)
    setBriefError(null)
    try {
      const { success, brief: generated } = await generateMorningBrief(projectId)
      if (success && generated) setBrief(generated)
      else setBriefError('Brief could not be generated.')
    } catch (e) {
      setBriefError(e instanceof Error ? e.message : 'Brief could not be generated.')
    } finally {
      setRegenerating(false)
    }
  }, [projectId])

  // Fetch todos
  useEffect(() => {
    if (!projectId) return
    let cancelled = false
    setLoadingTodos(true)
    setErrorTodos(null)
    getTodos(projectId).then(({ todos }) => {
      if (!cancelled) {
        setTodos(todos)
        setLoadingTodos(false)
      }
    }).catch((err) => {
      if (!cancelled) {
        setErrorTodos(err instanceof Error ? err.message : 'Failed to load tasks')
        setLoadingTodos(false)
      }
    })
    return () => { cancelled = true }
  }, [projectId])

  // Fetch sessions
  useEffect(() => {
    if (!projectId) return
    let cancelled = false
    setLoadingSessions(true)
    getSessions(projectId).then(({ sessions }) => {
      if (!cancelled) {
        setSessions(sessions)
        setLoadingSessions(false)
      }
    }).catch(() => {
      if (!cancelled) setLoadingSessions(false)
    })
    return () => { cancelled = true }
  }, [projectId])

  // Live agent metrics (15 s), host resources (5 s), today's usage (60 s).
  // usePolling pauses while the window is hidden.
  usePolling(async () => {
    if (projectId) setLiveMetrics(await getLiveMetrics(projectId))
  }, 15000, [projectId], !!projectId)
  usePolling(async () => { setSystem(await getSystemMetrics(false)) }, 5000)
  usePolling(async () => { setUsage(await getUsageSummary('today')) }, 60000)

  // Typewriter
  useEffect(() => {
    let i = 0
    const iv = setInterval(() => {
      if (i <= greeting.length) { setTyped(greeting.slice(0, i)); i++ }
      else clearInterval(iv)
    }, 38)
    return () => clearInterval(iv)
  }, [greeting])

  // Mouse parallax
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!heroRef.current) return
    const rect = heroRef.current.getBoundingClientRect()
    mouseX.set(((e.clientX - rect.left) / rect.width - 0.5) * 20)
    mouseY.set(((e.clientY - rect.top) / rect.height - 0.5) * 12)
  }, [mouseX, mouseY])

  // Close selector on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (selectorRef.current && !selectorRef.current.contains(e.target as Node)) {
        setSelectorOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const handleProjectSelect = useCallback((id: string) => {
    if (id) onProjectChange?.(id)
    setSelectorOpen(false)
  }, [onProjectChange])

  const handleToggleTodo = useCallback(async (todo: Todo) => {
    const newStatus = todo.status === 'done' ? 'pending' : 'done'
    setTogglingTodo(todo.id)
    // optimistic
    setTodos(prev => prev.map(t => t.id === todo.id ? { ...t, status: newStatus } : t))
    try {
      const res = await updateTodoStatus(projectId!, todo.id, newStatus)
      if (!res.success) {
        // revert
        setTodos(prev => prev.map(t => t.id === todo.id ? { ...t, status: todo.status } : t))
      }
    } catch {
      setTodos(prev => prev.map(t => t.id === todo.id ? { ...t, status: todo.status } : t))
    } finally {
      setTogglingTodo(null)
    }
  }, [projectId])

  const handleRefreshActivity = useCallback(() => {
    if (!projectId) return
    setLoadingActivity(true)
    setErrorActivity(null)
    getActivityFeed(projectId, 10).then(({ items }) => {
      setActivityItems(items)
      setLoadingActivity(false)
    }).catch((err) => {
      setErrorActivity(err instanceof Error ? err.message : 'Failed to load activity')
      setLoadingActivity(false)
    })
  }, [projectId])

  // Derived
  const dbOk = health?.db?.db === 'connected'
  const apiOk = health?.api === 'ok'
  const bedrockConfigured = health?.bedrock === 'configured'
  const embeddingConfigured = health?.embedding === 'configured'

  const commits = useMemo(() => activityItems.filter(item => item.kind === 'commit'), [activityItems])
  const commitsToday = useMemo(() => {
    // Compare in local time: an evening commit is "today" even if UTC rolled over.
    const today = new Date().toDateString()
    return commits.filter(item => item.created_at && new Date(item.created_at).toDateString() === today).length
  }, [commits])

  const tasksTotal = todos.length
  const tasksDone = todos.filter(t => t.status === 'done').length
  const tasksPending = todos.filter(t => t.status === 'pending').length

  const sessionStats = analytics?.session_stats || { total_sessions: 0, total_time_seconds: 0 }
  const sessionDuration = formatDuration(sessionStats.total_time_seconds)
  const activeDaysCount = analytics?.commits_over_time?.length || 0
  const commitsThisWeek = analytics?.commits_over_time?.reduce((sum, c) => sum + c.count, 0) || 0

  // Real readiness score from the backend, not a hard-coded number.
  const memHealth = Math.round(
    liveMetrics?.performance.module_health.find(m => m.name === 'Memory Engine')?.pct ?? 0,
  )

  const suggestions = useMemo(() => {
    const items: { label: string; action: string; icon: any }[] = []
    if (!brief && projectId && !loadingBrief) {
      items.push({ label: 'Generate Morning Brief', action: 'chat', icon: Sparkles })
    }
    if (tasksPending > 0) {
      items.push({ label: 'Review Pending Tasks', action: 'chat', icon: CheckSquare })
    }
    if (commits.length > 0) {
      items.push({ label: 'Query Memory', action: 'memory', icon: Brain })
    }
    items.push({ label: 'Start Work', action: 'chat', icon: Play })
    items.push({ label: 'View Activity', action: 'activity', icon: Activity })
    items.push({ label: 'Restore Workspace', action: 'restore', icon: RotateCcw })
    items.push({ label: 'Manage Projects', action: 'projects', icon: Folder })
    return items
  }, [brief, tasksPending, commits.length, projectId, loadingBrief])

  const agentStatus: 'ready' | 'starting' | 'disconnected' | 'unavailable' | 'error' =
    healthLoading ? 'starting' : (apiOk ? 'ready' : (health === null ? 'disconnected' : 'error'))

  const agentStatusLabel = {
    ready: 'Agent ready',
    starting: 'Starting…',
    disconnected: 'Disconnected',
    unavailable: 'Unavailable',
    error: 'Error',
  }[agentStatus]

  const agentBadgeState = agentStatus === 'ready' ? 'idle' : (agentStatus === 'starting' ? 'thinking' : 'offline')

  // Render project selector
  const renderProjectSelector = () => (
    <div ref={selectorRef} style={{ position: 'relative' }}>
      <button
        onClick={() => setSelectorOpen(v => !v)}
        style={{
          display: 'flex', alignItems: 'center', gap: '0.5rem',
          padding: '0.5rem 0.9rem',
          borderRadius: 'var(--r-md)',
          border: '1px solid var(--border-soft)',
          background: 'var(--bg-glass)',
          color: 'var(--text-secondary)',
          fontSize: '0.8rem',
          cursor: 'pointer',
          fontFamily: 'var(--font-sans)',
        }}
      >
        <Folder size={14} color="var(--accent)" />
        <span style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {currentProject?.name || 'Select project'}
        </span>
        <ChevronRight size={12} style={{ transform: selectorOpen ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }} />
      </button>
      {selectorOpen && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          style={{
            position: 'absolute', top: '100%', left: 0, marginTop: 4,
            minWidth: 240, maxHeight: 320, overflowY: 'auto',
            background: 'var(--bg-frosted)',
            backdropFilter: 'var(--blur-lg)',
            border: '1px solid var(--border-glass)',
            borderRadius: 'var(--r-md)',
            boxShadow: 'var(--shadow-lg)',
            zIndex: 50,
            padding: '0.5rem',
          }}
        >
          {projects.length === 0 ? (
            <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>
              No projects registered
            </div>
          ) : (
            projects.map(p => (
              <button
                key={p.id}
                onClick={() => handleProjectSelect(p.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '0.5rem',
                  width: '100%', padding: '0.5rem 0.6rem',
                  borderRadius: 'var(--r-sm)',
                  border: 'none',
                  background: p.id === projectId ? 'var(--accent-muted)' : 'transparent',
                  color: p.id === projectId ? 'var(--accent-2)' : 'var(--text-secondary)',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                  textAlign: 'left',
                  fontFamily: 'var(--font-sans)',
                }}
              >
                <Folder size={12} />
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</span>
                {p.id === projectId && <Check size={12} color="var(--accent)" />}
              </button>
            ))
          )}
          <div style={{ borderTop: '1px solid var(--border-soft)', marginTop: '0.5rem', paddingTop: '0.5rem' }}>
            <button
              onClick={() => { setSelectorOpen(false); onNavigate('projects') }}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.5rem',
                width: '100%', padding: '0.5rem 0.6rem',
                borderRadius: 'var(--r-sm)',
                border: 'none',
                background: 'transparent',
                color: 'var(--text-tertiary)',
                fontSize: '0.8rem',
                cursor: 'pointer',
                textAlign: 'left',
                fontFamily: 'var(--font-sans)',
              }}
            >
              <Plus size={12} />
              Manage Projects
            </button>
          </div>
        </motion.div>
      )}
    </div>
  )

  // Empty state for no project
  if (!projectsLoading && projects.length === 0) {
    return (
      <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <motion.div initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', stiffness: 200, damping: 24 }}>
          <GlassCard padding="2rem" style={{ textAlign: 'center' }}>
            <FolderOpen size={48} color="var(--text-disabled)" style={{ marginBottom: '1rem' }} />
            <h2 style={{ marginBottom: '0.5rem' }}>No projects registered</h2>
            <p style={{ color: 'var(--text-tertiary)', marginBottom: '1.5rem', fontSize: '0.85rem' }}>
              Register your first project to start using Autometa's developer command center.
            </p>
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => onNavigate('projects')}
              style={{
                padding: '0.6rem 1.2rem',
                borderRadius: 'var(--r-md)',
                border: 'none',
                background: 'linear-gradient(135deg, var(--accent) 0%, #8b6fff 100%)',
                color: '#fff',
                fontSize: '0.85rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Create First Project
            </motion.button>
          </GlassCard>
        </motion.div>
      </div>
    )
  }

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
        <motion.div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
          <motion.span style={{
            position: 'absolute', top: '-40%', right: '10%',
            width: 260, height: 260,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(108,79,255,0.12) 0%, transparent 70%)',
            x: springX, y: springY,
          }} />
          <motion.span style={{
            position: 'absolute', top: '10%', right: '40%',
            width: 180, height: 180,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(34,211,238,0.08) 0%, transparent 70%)',
            x: springX, y: springY,
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
                  {new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
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
                {projectId
                  ? (brief?.highlights?.[0] || 'Your AI memory engine has been running. Here is what you need to know.')
                  : 'Select a project to view your AI memory engine status.'}
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
                {renderProjectSelector()}
                <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                  {branchLoading ? 'Loading branch…' : (branch ? `Branch: ${branch}` : (branchError ? 'Branch unavailable' : 'No branch'))}
                </span>
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.5rem' }}>
              <AIStatusBadge state={agentBadgeState} label={agentStatusLabel} size="md" />
              {healthLoading && <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>Connecting…</span>}
              <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                {liveMetrics ? (liveMetrics.agent.reasoning_backend === 'available' ? 'AI ready' : 'AI unavailable') : 'AI status…'} · {health?.embedding === 'configured' ? 'embeddings on' : 'no embeddings'}
              </span>
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
          { icon: GitCommit, label: 'Commits Today', value: `${commitsToday}`, color: 'var(--info)', ring: commitsToday > 0 ? 60 : 0 },
          { icon: CheckSquare, label: 'Tasks Done', value: `${tasksDone}/${tasksTotal}`, color: 'var(--accent-2)', ring: tasksTotal > 0 ? (tasksDone / tasksTotal) * 100 : 0 },
          { icon: Clock, label: 'Session Time', value: sessionDuration, color: 'var(--warning)', ring: sessionStats.total_time_seconds > 0 ? Math.min(100, (sessionStats.total_time_seconds / 3600) * 20) : 0 },
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
                      {loadingAnalytics && !analytics ? '—' : stat.value}
                    </span>
                  </div>
                  <ProgressRing value={stat.ring} size={46} stroke={4} color={stat.color} glow />
                </div>
              </GlassCard>
            </motion.div>
          )
        })}
      </motion.div>

      {/* ── Active Project card ──────────────────────────────────────────── */}
      <motion.div variants={cardVariant} initial="hidden" animate="show">
        <GlassCard padding="1.5rem" hoverable style={{ position: 'relative', overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{
                width: 44, height: 44, borderRadius: 10,
                background: 'linear-gradient(135deg, var(--accent) 0%, var(--ai-cyan) 100%)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: 'var(--shadow-glow)',
              }}>
                <Folder size={20} color="#fff" />
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <h2 style={{ fontSize: '1.1rem', margin: 0 }}>{currentProject?.name || 'Loading…'}</h2>
                  <span style={{
                    fontSize: '0.6rem', background: 'var(--success-muted)', color: 'var(--success)',
                    padding: '0.15rem 0.5rem', borderRadius: 'var(--r-full)', fontWeight: 600,
                  }}>ACTIVE</span>
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', marginTop: 2, wordBreak: 'break-all' }}>
                  {currentProject?.repo_path || '—'}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <motion.button
                whileHover={{ scale: 1.03, y: -1 }}
                whileTap={{ scale: 0.97 }}
                onClick={() => onNavigate('chat')}
                style={{
                  display: 'flex', alignItems: 'center', gap: '0.4rem',
                  padding: '0.55rem 1.1rem',
                  borderRadius: 'var(--r-md)',
                  border: 'none',
                  background: 'linear-gradient(135deg, var(--accent) 0%, #8b6fff 100%)',
                  color: '#fff',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  boxShadow: 'var(--shadow-glow)',
                }}
              >
                <Play size={14} /> Start Work
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={() => onNavigate('projects')}
                style={{
                  display: 'flex', alignItems: 'center', gap: '0.4rem',
                  padding: '0.55rem 1rem',
                  borderRadius: 'var(--r-md)',
                  border: '1px solid var(--border-soft)',
                  background: 'var(--bg-glass)',
                  color: 'var(--text-secondary)',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                }}
              >
                <FolderOpen size={14} /> Open Project
              </motion.button>
            </div>
          </div>

          {/* Project details grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
            {[
              { label: 'Git Branch', value: branchLoading ? 'Loading…' : (branch || '—'), icon: GitBranch, color: 'var(--ai-cyan)' },
              { label: 'Recent Activity', value: activityItems.length > 0 ? formatRelativeTime(activityItems[0].created_at) : 'No activity', icon: Clock, color: 'var(--warning)' },
              { label: 'Current Task', value: tasksPending > 0 ? `${tasksPending} pending` : 'All done', icon: CheckSquare, color: 'var(--accent-2)' },
              { label: 'Availability', value: apiOk && dbOk ? 'Ready' : 'Degraded', icon: Zap, color: apiOk && dbOk ? 'var(--success)' : 'var(--warning)' },
            ].map(({ label, value, icon: Icon, color }) => (
              <div key={label} style={{
                padding: '0.75rem',
                background: 'var(--bg-elevated)',
                borderRadius: 'var(--r-sm)',
                border: '1px solid var(--border-soft)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.3rem' }}>
                  <Icon size={12} color={color} />
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', fontWeight: 500 }}>{label}</span>
                </div>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-primary)', fontWeight: 500 }}>{value}</span>
              </div>
            ))}
          </div>

          {/* Working tree status */}
          {liveMetrics?.memory?.changed_files !== undefined && (
            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
              Working tree: {liveMetrics.memory.changed_files} changed file{liveMetrics.memory.changed_files !== 1 ? 's' : ''}
              {liveMetrics.memory.changed_files === 0 && ' · clean'}
            </div>
          )}
        </GlassCard>
      </motion.div>

      {/* ── Morning brief + today's usage ─────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(240px, 1fr)', gap: '1rem' }}>
        <GlassCard hoverable={false} glowing>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Sun size={15} color="var(--warning)" />
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>Morning Brief</span>
              {brief?.brief_date && (
                <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{brief.brief_date}</span>
              )}
            </div>
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              <button onClick={handleRegenerateBrief} disabled={regenerating || !projectId} style={smallButton} title="Regenerate from latest activity">
                {regenerating ? <Loader2 size={12} className="spin" /> : <RefreshCw size={12} />} Refresh
              </button>
              <button onClick={() => onNavigate('restore')} disabled={!projectId} style={{ ...smallButton, borderColor: 'var(--accent)', color: 'var(--accent-2)' }}>
                <RotateCcw size={12} /> Restore & continue
              </button>
            </div>
          </div>
          {loadingBrief && !brief && <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>Preparing brief…</div>}
          {briefError && <div style={{ fontSize: '0.75rem', color: 'var(--error)', marginBottom: '0.5rem' }}>{briefError}</div>}
          {!loadingBrief && !brief && !briefError && (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>No memory found for this project yet.</div>
          )}
          {brief && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.9rem', fontSize: '0.8rem' }}>
              <div>
                <div style={briefLabel}>Highlights · {brief.commits_count} commit{brief.commits_count === 1 ? '' : 's'}</div>
                {brief.highlights.length === 0
                  ? <div style={{ color: 'var(--text-tertiary)' }}>No recent activity recorded.</div>
                  : brief.highlights.slice(0, 5).map((h, i) => <div key={i} style={briefItem}><span style={{ color: 'var(--accent)' }}>•</span>{h}</div>)}
                {brief.last_edited_file && (
                  <div style={{ ...briefItem, color: 'var(--text-tertiary)', marginTop: 4 }}>
                    <FileCode size={12} style={{ flexShrink: 0, marginTop: 2 }} />Last edited: <span style={{ fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>{brief.last_edited_file}</span>
                  </div>
                )}
              </div>
              <div>
                <div style={briefLabel}>Pending</div>
                {brief.pending_items.length === 0
                  ? <div style={{ color: 'var(--text-tertiary)' }}>No pending items.</div>
                  : brief.pending_items.slice(0, 5).map((h, i) => <div key={i} style={briefItem}><span style={{ color: 'var(--warning)' }}>•</span>{h}</div>)}
              </div>
            </div>
          )}
        </GlassCard>

        <GlassCard hoverable onClick={() => onNavigate('resources')}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.75rem' }}>
            <Clock size={15} color="var(--ai-cyan)" />
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>Today’s app usage</span>
          </div>
          {!usage ? (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>Loading…</div>
          ) : usage.total_seconds === 0 ? (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
              {usage.tracking?.running ? 'Recording — no active time yet today.' : 'Usage tracking is not running.'}
            </div>
          ) : (
            <>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}>
                {formatDuration(usage.total_seconds)}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: '0.6rem' }}>
                active · {usage.focus_percent}% development
              </div>
              {usage.apps.slice(0, 4).map(a => (
                <div key={a.app} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', padding: '0.2rem 0', gap: '0.5rem' }}>
                  <span style={{ color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.app}</span>
                  <span style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', flexShrink: 0 }}>{formatDuration(a.seconds)}</span>
                </div>
              ))}
            </>
          )}
        </GlassCard>
      </div>

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
              <div style={{ display: 'flex', gap: '0.4rem' }}>
                <button
                  onClick={handleRefreshActivity}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center' }}
                  title="Refresh"
                >
                  <RefreshCw size={12} />
                </button>
                <button onClick={() => onNavigate('activity')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', gap: 2 }}>
                  <span style={{ fontSize: '0.65rem' }}>All</span><ChevronRight size={12} />
                </button>
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {loadingActivity && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem', color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>
                  Loading activity…
                </div>
              )}
              {errorActivity && (
                <div style={{ padding: '0.75rem', background: 'var(--error-muted)', borderRadius: 'var(--r-sm)', color: 'var(--error)', fontSize: '0.75rem' }}>
                  {errorActivity}
                  <button onClick={handleRefreshActivity} style={{ marginLeft: 8, background: 'none', border: 'none', color: 'var(--error)', cursor: 'pointer', textDecoration: 'underline', fontSize: '0.75rem' }}>Retry</button>
                </div>
              )}
              {!loadingActivity && !errorActivity && commits.slice(0, 5).map((c, i) => (
                <motion.div
                  key={c.id || i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.08, type: 'spring', stiffness: 300, damping: 28 }}
                  style={{
                    display: 'flex', flexDirection: 'column', gap: '0.15rem',
                    padding: '0.55rem 0.7rem',
                    background: 'var(--bg-elevated)',
                    borderRadius: 'var(--r-sm)',
                    border: '1px solid var(--border-soft)',
                  }}
                >
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', lineHeight: 1.3 }}>{c.summary}</span>
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>{formatRelativeTime(c.created_at || '')}</span>
                    {c.detail && (
                      <span style={{ fontSize: '0.62rem', background: 'var(--accent-muted)', color: 'var(--accent-2)', padding: '0 0.35rem', borderRadius: 3 }}>{c.detail}</span>
                    )}
                  </div>
                </motion.div>
              ))}
              {!loadingActivity && !errorActivity && commits.length === 0 && (
                <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>
                  {activityItems.length === 0 ? 'No commits found' : 'No commits in recent activity'}
                </div>
              )}
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
                animate={{ width: `${tasksTotal > 0 ? (tasksDone / tasksTotal) * 100 : 0}%` }}
                transition={{ duration: 1, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
                style={{ height: '100%', background: 'linear-gradient(90deg, var(--accent) 0%, var(--ai-cyan) 100%)', borderRadius: 99 }}
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', maxHeight: 260, overflowY: 'auto' }}>
              {loadingTodos && (
                <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>
                  Loading tasks…
                </div>
              )}
              {errorTodos && (
                <div style={{ padding: '0.75rem', background: 'var(--error-muted)', borderRadius: 'var(--r-sm)', color: 'var(--error)', fontSize: '0.75rem' }}>
                  {errorTodos}
                </div>
              )}
              {!loadingTodos && !errorTodos && todos.length === 0 && (
                <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>
                  No pending tasks
                </div>
              )}
              {!loadingTodos && !errorTodos && todos.slice(0, 8).map((todo, i) => (
                <motion.div
                  key={todo.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.1 + i * 0.07, type: 'spring', stiffness: 300, damping: 28 }}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '0.6rem',
                    padding: '0.45rem 0.6rem',
                    borderRadius: 'var(--r-sm)',
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border-soft)',
                    opacity: todo.status === 'done' ? 0.6 : 1,
                  }}
                >
                  <button
                    onClick={() => handleToggleTodo(todo)}
                    disabled={togglingTodo === todo.id}
                    style={{
                      width: 18, height: 18, borderRadius: 4,
                      border: `1.5px solid ${todo.status === 'done' ? 'var(--success)' : 'var(--border-hard)'}`,
                      background: todo.status === 'done' ? 'var(--success)' : 'transparent',
                      cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      flexShrink: 0,
                      padding: 0,
                    }}
                  >
                    {togglingTodo === todo.id ? (
                      <Loader2 size={10} color="var(--text-tertiary)" className="spin" />
                    ) : (todo.status === 'done' ? <Check size={11} color="#fff" /> : null)}
                  </button>
                  <span style={{
                    fontSize: '0.78rem',
                    color: todo.status === 'done' ? 'var(--text-tertiary)' : 'var(--text-secondary)',
                    flex: 1,
                    textDecoration: todo.status === 'done' ? 'line-through' : 'none',
                  }}>
                    {todo.description}
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
                {suggestions.map((s, i) => {
                  const Icon = s.icon
                  return (
                    <motion.button
                      key={i}
                      onClick={() => onNavigate(s.action)}
                      whileHover={{ x: 4 }}
                      whileTap={{ scale: 0.97 }}
                      transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                      style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
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
                      <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Icon size={13} color="var(--ai-cyan)" />
                        {s.label}
                      </span>
                      <ChevronRight size={14} color="var(--ai-cyan)" />
                    </motion.button>
                  )
                })}
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
                {loadingSessions && (
                  <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>
                    Loading sessions…
                  </div>
                )}
                {!loadingSessions && sessions.length > 0 && (
                  <>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid var(--border-soft)' }}>
                      <div>
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-primary)', fontWeight: 500 }}>Total Sessions</div>
                        <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', marginTop: 1 }}>{sessions.length} recorded</div>
                      </div>
                      <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{sessionDuration}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.5rem 0' }}>
                      <div>
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-primary)', fontWeight: 500 }}>Active Days</div>
                        <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', marginTop: 1 }}>{activeDaysCount} days</div>
                      </div>
                      <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{commitsThisWeek} commits</span>
                    </div>
                    {sessions.slice(0, 3).map((s, i) => (
                      <div key={s.id || i} style={{
                        padding: '0.4rem 0.6rem',
                        background: 'var(--bg-elevated)',
                        borderRadius: 'var(--r-sm)',
                        fontSize: '0.72rem',
                        color: 'var(--text-secondary)',
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span>{new Date(s.started_at).toLocaleDateString()}</span>
                          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>
                            {s.ended_at ? formatDuration((new Date(s.ended_at).getTime() - new Date(s.started_at).getTime()) / 1000) : 'active'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </>
                )}
                {!loadingSessions && sessions.length === 0 && (
                  <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>
                    No sessions recorded
                  </div>
                )}
              </div>
            </GlassCard>
          </motion.div>
        </div>
      </motion.div>

      {/* ── System health row ────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, type: 'spring', stiffness: 200, damping: 24 }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-tertiary)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            System Health
          </h3>
          <button onClick={() => onNavigate('resources')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: 2 }}>
            Details <ChevronRight size={12} />
          </button>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          {[
            { label: 'Backend API', ok: apiOk, icon: Zap },
            { label: 'CockroachDB', ok: dbOk, icon: Activity },
            { label: 'Memory Engine', ok: dbOk, icon: Brain },
            { label: 'Reasoning', ok: liveMetrics?.agent.reasoning_backend === 'available', icon: Terminal },
            { label: 'Projects', ok: projects.length > 0, icon: FolderOpen },
            { label: 'Bedrock', ok: bedrockConfigured, icon: Sparkles },
            { label: 'Embeddings', ok: embeddingConfigured, icon: Cpu },
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
              title={ok ? 'Healthy' : 'Unavailable'}
            >
              <Icon size={12} color={ok ? 'var(--success)' : 'var(--error)'} />
              <span style={{ fontSize: '0.7rem', color: ok ? 'var(--success)' : 'var(--error)', fontWeight: 500 }}>{label}</span>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: ok ? 'var(--success)' : 'var(--error)', marginLeft: 2 }} />
            </div>
          ))}
        </div>

        {/* Live host resources */}
        <div style={{ marginTop: '0.75rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.75rem' }}>
          {[
            { label: 'CPU', icon: Cpu, pct: system?.cpu?.percent ?? null, sub: system?.cpu ? `${system.cpu.cores_logical} threads` : '' },
            { label: 'Memory (RAM)', icon: MemoryStick, pct: system?.memory?.percent ?? null, sub: system?.memory ? `${system.memory.used_gb.toFixed(1)} / ${system.memory.total_gb.toFixed(0)} GB` : '' },
            { label: 'GPU', icon: Monitor, pct: system?.gpu?.devices?.[0]?.utilization_percent ?? null, sub: system?.gpu?.devices?.[0]?.name ?? 'Not available' },
            { label: 'Disk', icon: HardDrive, pct: system?.disk?.percent ?? null, sub: system?.disk?.total_gb ? `${system.disk.used_gb} / ${system.disk.total_gb} GB` : '' },
          ].map(({ label, icon: Icon, pct, sub }) => (
            <GlassCard key={label} padding="0.75rem" hoverable onClick={() => onNavigate('resources')}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.3rem' }}>
                    <Icon size={12} color="var(--text-tertiary)" />
                    <span style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)' }}>{label}</span>
                  </div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: pct === null ? 'var(--text-disabled)' : 'var(--text-primary)', fontFamily: 'var(--font-display)', fontVariantNumeric: 'tabular-nums' }}>
                    {pct === null ? '—' : `${Math.round(pct)}%`}
                  </div>
                  <div style={{ fontSize: '0.62rem', color: 'var(--text-tertiary)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {system ? sub : 'Connecting…'}
                  </div>
                </div>
                <ProgressRing value={pct ?? 0} size={38} stroke={4} color={pct !== null && pct >= 85 ? 'var(--error)' : pct !== null && pct >= 65 ? 'var(--warning)' : 'var(--success)'} animate={false} />
              </div>
            </GlassCard>
          ))}
        </div>
      </motion.div>
    </div>
  )
}

const smallButton: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 4,
  padding: '0.3rem 0.65rem', borderRadius: 'var(--r-sm)',
  border: '1px solid var(--border-soft)', background: 'var(--bg-elevated)',
  color: 'var(--text-secondary)', fontSize: '0.7rem', cursor: 'pointer', fontFamily: 'var(--font-sans)',
}

const briefLabel: React.CSSProperties = {
  fontSize: '0.66rem', color: 'var(--text-tertiary)', textTransform: 'uppercase',
  letterSpacing: '0.07em', marginBottom: '0.4rem', fontWeight: 600,
}

const briefItem: React.CSSProperties = {
  display: 'flex', gap: '0.4rem', lineHeight: 1.5, color: 'var(--text-secondary)', marginBottom: 2,
}
