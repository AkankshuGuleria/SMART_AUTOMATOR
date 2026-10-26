/**
 * screens/WorkspaceRestoreScreen.tsx
 * Cinematic step-by-step workspace restoration with real-time status and particle ambient.
 * Data sourced from POST /projects/{projectId}/restore.
 */
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  GitBranch, Terminal as TerminalIcon, Monitor,
  Globe, Server,
  CheckCircle2, Loader2, Circle,
  Play, RefreshCw, Sparkles,
} from 'lucide-react'
import GlassCard from '../components/ui/GlassCard'
import AIStatusBadge from '../components/ui/AIStatusBadge'
import {
  restoreWorkspace,
  getProject,
  AgentSocket,
  type Project,
  type RestoreStep,
  type RestoreResult,
} from '../lib/api'

interface WorkspaceRestoreScreenProps {
  projectId?: string
}

type StepStatus = 'pending' | 'running' | 'done' | 'error' | 'skipped'

interface UiStepConfig {
  label: string
  description: string
  icon: React.FC<{ size?: number; strokeWidth?: number }>
  color: string
}

const STEP_UI_CONFIG: Record<string, UiStepConfig> = {
  git_checkout: {
    label: 'Git Restoration',
    description: 'Checking out branch, fetching recent commits…',
    icon: GitBranch,
    color: 'var(--info)',
  },
  terminal: {
    label: 'Terminal Launch',
    description: 'Opening terminal at project root…',
    icon: TerminalIcon,
    color: 'var(--success)',
  },
  dev_servers: {
    label: 'Dev Servers',
    description: 'Starting backend, frontend, and any configured servers…',
    icon: Server,
    color: 'var(--info)',
  },
  editor: {
    label: 'Editor Launch',
    description: 'Opening VS Code with last workspace state…',
    icon: Monitor,
    color: 'var(--warning)',
  },
  browser: {
    label: 'Browser Restore',
    description: 'Restoring tab groups and dev server tabs…',
    icon: Globe,
    color: 'var(--ai-cyan)',
  },
}

const DEFAULT_STEP_UI: UiStepConfig = {
  label: 'Workspace Step',
  description: 'Executing…',
  icon: Circle,
  color: 'var(--text-tertiary)',
}

function getStepUi(stepName: string): UiStepConfig {
  return STEP_UI_CONFIG[stepName] ?? DEFAULT_STEP_UI
}

function apiStatusToUiStepStatus(status: string): StepStatus {
  switch (status) {
    case 'ok':      return 'done'
    case 'error':   return 'error'
    case 'skipped': return 'skipped'
    default:        return 'pending'
  }
}

const SEQUENTIAL_REVEAL_DELAY = 500

export default function WorkspaceRestoreScreen({ projectId }: WorkspaceRestoreScreenProps) {
  const [steps, setSteps] = useState<RestoreStep[]>([])
  const [statuses, setStatuses] = useState<Record<string, StepStatus>>({})
  const [currentStep, setCurrentStep] = useState(-1)
  const [aiReason, setAiReason] = useState('')
  const [isRunning, setIsRunning] = useState(false)
  const [done, setDone] = useState(false)
  const [overall, setOverall] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [project, setProject] = useState<Project | null>(null)
  const [projectLoading, setProjectLoading] = useState(true)

  // Subscribe to WebSocket restore_progress events
  useEffect(() => {
    const socket = new AgentSocket()
    socket.connect()
    
    socket.on('restore_progress' as any, (event: any) => {
      const data = event.data || {}
      if (projectId && data.project_id && data.project_id !== projectId) {
        return
      }
      if (data.steps) {
        setSteps(data.steps)
        setStatuses(Object.fromEntries(data.steps.map((s: RestoreStep) => [s.step, apiStatusToUiStepStatus(s.status)])))
      }
      if (typeof data.current_step === 'number') {
        setCurrentStep(data.current_step)
      }
      if (data.ai_reason) {
        setAiReason(data.ai_reason)
      }
      if (data.is_running !== undefined) {
        setIsRunning(data.is_running)
      }
      if (data.done !== undefined) {
        setDone(data.done)
      }
      if (data.error) {
        setError(data.error)
      }
    })
    
    return () => {
      socket.disconnect()
    }
  }, [projectId])

  // Fetch project info on mount
  useEffect(() => {
    if (!projectId) {
      setProject(null)
      setProjectLoading(false)
      return
    }

    let cancelled = false
    setProjectLoading(true)

    getProject(projectId)
      .then(({ project }) => {
        if (!cancelled) setProject(project)
      })
      .catch(() => {
        if (!cancelled) setProject(null)
      })
      .finally(() => {
        if (!cancelled) setProjectLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [projectId])

  const startRestore = async () => {
    if (!projectId) return
    setIsRunning(true)
    setDone(false)
    setError(null)
    setSteps([])
    setStatuses({})
    setCurrentStep(-1)
    setAiReason('')
    setOverall(null)

    try {
      const result: RestoreResult = await restoreWorkspace(projectId)
      setSteps(result.steps)
      setStatuses(Object.fromEntries(result.steps.map(s => [s.step, 'pending'])))

      for (let i = 0; i < result.steps.length; i++) {
        const step = result.steps[i]
        setCurrentStep(i)
        setAiReason(step.detail ?? `Executing ${step.step}…`)
        setStatuses(prev => ({ ...prev, [step.step]: 'running' }))

        await new Promise(r => setTimeout(r, SEQUENTIAL_REVEAL_DELAY))

        setStatuses(prev => ({ ...prev, [step.step]: apiStatusToUiStepStatus(step.status) }))
      }

      setCurrentStep(-1)
      setOverall(result.overall ?? null)
      if (result.overall && result.overall !== 'ok') {
        setAiReason(result.error ?? 'Restoration completed with some issues.')
      } else {
        setAiReason('All systems restored. Ready to code.')
      }
      setIsRunning(false)
      setDone(true)
    } catch (err) {
      setIsRunning(false)
      setError(err instanceof Error ? err.message : 'Restore failed')
    }
  }

  const completedCount = Object.values(statuses).filter(s => s === 'done' || s === 'skipped').length
  const progress = steps.length > 0 ? (completedCount / steps.length) * 100 : 0

  // Build the UI steps array for rendering (mapped from real API data)
  const uiSteps = steps.map((apiStep) => ({
    ...getStepUi(apiStep.step),
    ...apiStep,
  }))

  // ─── Screen states ─────────────────────────────────────────────────────

  if (!projectId) {
    return (
      <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', stiffness: 220, damping: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.25rem' }}>
            <RefreshCw size={20} color="var(--accent-2)" strokeWidth={2} />
            <h1>Workspace Restore</h1>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
            Restore your full development environment from persistent AI memory.
          </p>
        </motion.div>
        <div className="automata-empty">
          <p>Select a project to restore your workspace.</p>
        </div>
      </div>
    )
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', stiffness: 220, damping: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.25rem' }}>
          <RefreshCw size={20} color="var(--accent-2)" strokeWidth={2} />
          <h1>Workspace Restore</h1>
        </div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
          Restore your full development environment from persistent AI memory.
        </p>
      </motion.div>

      {/* Project card */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 200, damping: 24, delay: 0.05 }}
        style={{
          background: 'linear-gradient(135deg, rgba(108,79,255,0.08) 0%, rgba(34,211,238,0.05) 100%)',
          border: '1px solid var(--border-glow)',
          borderRadius: 'var(--r-xl)',
          padding: '1.5rem 2rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div>
          {projectLoading ? (
            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>Loading project…</div>
          ) : (
            <>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', marginBottom: '0.25rem', fontFamily: 'var(--font-mono)' }}>
                {project?.repo_path ?? projectId}
              </div>
              <h2 style={{ fontSize: '1.4rem', fontFamily: 'var(--font-display)', marginBottom: '0.4rem' }}>
                {project?.name ?? 'Project'}
              </h2>
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                {steps.some(s => s.step === 'git_checkout') && (() => {
                  const gitStep = steps.find(s => s.step === 'git_checkout')
                  const branchMatch = gitStep?.detail?.match(/branch '([^']+)'/)
                  const branch = branchMatch ? branchMatch[1] : 'main'
                  return (
                    <span style={{ fontSize: '0.72rem', color: 'var(--info)', fontFamily: 'var(--font-mono)' }}>⎇ {branch}</span>
                  )
                })()}
                <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>
                  Last session: {project?.created_at ? formatSessionDate(project.created_at) : '—'}
                </span>
              </div>
            </>
          )}
        </div>
        <motion.button
          onClick={startRestore}
          disabled={isRunning || projectLoading}
          whileHover={!isRunning && !projectLoading ? { scale: 1.04, boxShadow: '0 0 30px rgba(108,79,255,0.4)' } : undefined}
          whileTap={!isRunning && !projectLoading ? { scale: 0.97 } : undefined}
          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.6rem',
            padding: '0.75rem 1.5rem',
            borderRadius: 'var(--r-md)',
            border: 'none',
            background: isRunning ? 'var(--bg-elevated)' : 'linear-gradient(135deg, var(--accent) 0%, #8b6fff 100%)',
            color: isRunning ? 'var(--text-tertiary)' : '#fff',
            fontFamily: 'var(--font-sans)',
            fontWeight: 600,
            fontSize: '0.9rem',
            cursor: isRunning || projectLoading ? 'not-allowed' : 'pointer',
            boxShadow: isRunning ? 'none' : 'var(--shadow-glow)',
          }}
        >
          {isRunning ? (
            <><Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} /> Restoring…</>
          ) : done ? (
            <><RefreshCw size={18} /> Restore Again</>
          ) : (
            <><Play size={18} /> Start Restore</>
          )}
        </motion.button>
      </motion.div>

      {/* Restore error */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            style={{
              padding: '0.75rem 1rem',
              background: 'var(--error-muted)',
              border: '1px solid rgba(239,68,68,0.25)',
              borderRadius: 'var(--r-md)',
            }}
          >
            <span style={{ fontSize: '0.82rem', color: 'var(--error)' }}>{error}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Progress bar */}
      <AnimatePresence>
        {(isRunning || done) && uiSteps.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
          >
            <div style={{ height: 4, background: 'var(--bg-elevated)', borderRadius: 99, overflow: 'hidden' }}>
              <motion.div
                animate={{ width: `${progress}%` }}
                transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.5 }}
                style={{ height: '100%', background: 'linear-gradient(90deg, var(--accent) 0%, var(--ai-cyan) 100%)', borderRadius: 99 }}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.4rem' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{completedCount}/{uiSteps.length} steps</span>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{Math.round(progress)}%</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* AI reasoning */}
      <AnimatePresence>
        {isRunning && aiReason && (
          <motion.div
            key={aiReason}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 26 }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              padding: '0.75rem 1rem',
              background: 'var(--ai-purple-muted)',
              border: '1px solid rgba(168,85,247,0.2)',
              borderRadius: 'var(--r-md)',
            }}
          >
            <AIStatusBadge state="thinking" size="sm" />
            <span style={{ fontSize: '0.82rem', color: 'var(--ai-purple)', fontStyle: 'italic' }}>{aiReason}</span>
          </motion.div>
        )}
        {done && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 26 }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              padding: '0.75rem 1rem',
              background: overall === 'ok' || !overall ? 'var(--success-muted)' : overall === 'partial' ? 'var(--warning-muted)' : 'var(--error-muted)',
              border: `1px solid ${overall === 'ok' || !overall ? 'rgba(16,185,129,0.25)' : overall === 'partial' ? 'rgba(245,158,11,0.3)' : 'rgba(239,68,68,0.3)'}`,
              borderRadius: 'var(--r-md)',
            }}
          >
            <Sparkles size={16} color={overall === 'ok' || !overall ? 'var(--success)' : overall === 'partial' ? 'var(--warning)' : 'var(--error)'} />
            <span style={{ fontSize: '0.85rem', color: overall === 'ok' || !overall ? 'var(--success)' : overall === 'partial' ? 'var(--warning)' : 'var(--error)', fontWeight: 500 }}>
              {overall === 'ok' || !overall
                ? "Workspace restored. You're ready to continue where you left off."
                : overall === 'partial'
                  ? 'Workspace partly restored — check the failed steps below.'
                  : 'Restore failed — see the first failed step below.'}
            </span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Steps */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
        {uiSteps.map((step, i) => {
          const status = statuses[step.step] ?? 'pending'
          const cfg = getStepUi(step.step)
          const Icon = cfg.icon
          const isCurrentStep = currentStep === i
          return (
            <motion.div
              key={step.step}
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.04, type: 'spring', stiffness: 280, damping: 26 }}
            >
              <GlassCard
                padding="1rem"
                style={{
                  borderLeft: `3px solid ${status === 'done' || status === 'skipped' ? cfg.color : status === 'running' ? cfg.color : 'var(--border-soft)'}`,
                  opacity: status === 'pending' && isRunning ? 0.55 : 1,
                  transition: 'opacity var(--dur-base) var(--ease-in-out)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
                  {/* Step icon */}
                  <motion.div
                    animate={isCurrentStep ? { rotate: [0, 8, -8, 0] } : {}}
                    transition={{ duration: 0.5, repeat: isCurrentStep ? Infinity : 0 }}
                    style={{
                      width: 36, height: 36,
                      borderRadius: 'var(--r-sm)',
                      background: status === 'done' || status === 'skipped' || status === 'running' ? cfg.color + '20' : 'var(--bg-elevated)',
                      border: `1.5px solid ${status === 'done' || status === 'skipped' || status === 'running' ? cfg.color : 'var(--border-soft)'}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      flexShrink: 0,
                      boxShadow: isCurrentStep ? `0 0 16px ${cfg.color}50` : 'none',
                      transition: 'all var(--dur-base) var(--ease-in-out)',
                    }}
                  >
                    <span style={{ color: status === 'done' || status === 'skipped' || status === 'running' ? cfg.color : 'var(--text-tertiary)', display: 'flex' }}>
                      <Icon size={17} strokeWidth={2} />
                    </span>
                  </motion.div>

                  {/* Content */}
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '0.85rem', fontWeight: 600, color: status === 'pending' && !isRunning ? 'var(--text-tertiary)' : 'var(--text-primary)', marginBottom: '0.15rem' }}>
                      {cfg.label}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{step.detail ?? cfg.description}</div>
                  </div>

                  {/* Status icon */}
                  <div style={{ flexShrink: 0 }}>
                    {status === 'done' && (
                      <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 500, damping: 20 }}>
                        <CheckCircle2 size={20} color={cfg.color} />
                      </motion.div>
                    )}
                    {status === 'skipped' && (
                      <Circle size={18} color={cfg.color} fill={cfg.color} />
                    )}
                    {status === 'running' && (
                      <Loader2 size={18} style={{ animation: 'spin 1s linear infinite', color: cfg.color }} />
                    )}
                    {status === 'error' && (
                      <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 500, damping: 20 }}>
                        <CheckCircle2 size={20} color="var(--error)" />
                      </motion.div>
                    )}
                    {status === 'pending' && (
                      <Circle size={18} color="var(--text-disabled)" />
                    )}
                  </div>
                </div>
              </GlassCard>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

function formatSessionDate(isoDate: string): string {
  try {
    const date = new Date(isoDate)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
    if (diffDays < 1) return 'Today'
    if (diffDays < 2) return 'Yesterday'
    if (diffDays < 7) return `${diffDays} days ago`
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  } catch {
    return '—'
  }
}