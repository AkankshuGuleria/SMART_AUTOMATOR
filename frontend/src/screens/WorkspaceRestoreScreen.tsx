/**
 * screens/WorkspaceRestoreScreen.tsx
 * Cinematic step-by-step workspace restoration with real-time status and particle ambient.
 */
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  GitBranch, Terminal as TerminalIcon, Monitor,
  Globe, Brain, CheckCircle2, Loader2, Circle,
  Play, RefreshCw, Sparkles,
} from 'lucide-react'
import GlassCard from '../components/ui/GlassCard'
import AIStatusBadge from '../components/ui/AIStatusBadge'

interface RestoreStep {
  id: string
  label: string
  description: string
  icon: React.FC<{ size?: number; strokeWidth?: number }>
  color: string
  duration: number
}

const STEPS: RestoreStep[] = [
  { id: 'memory', label: 'Memory Retrieval', description: 'Loading your last session context and project state…', icon: Brain, color: 'var(--ai-purple)', duration: 1800 },
  { id: 'git', label: 'Git Restoration', description: 'Checking out branch, fetching recent commits…', icon: GitBranch, color: 'var(--info)', duration: 1400 },
  { id: 'terminal', label: 'Terminal Launch', description: 'Opening terminal at project root…', icon: TerminalIcon, color: 'var(--success)', duration: 900 },
  { id: 'editor', label: 'Editor Launch', description: 'Opening VS Code with last workspace state…', icon: Monitor, color: 'var(--warning)', duration: 1200 },
  { id: 'browser', label: 'Browser Restore', description: 'Restoring tab groups and dev server tabs…', icon: Globe, color: 'var(--ai-cyan)', duration: 1100 },
]

type StepStatus = 'pending' | 'running' | 'done' | 'error'

const DEMO_PROJECT = {
  name: 'AUTOMATA',
  path: 'D:/AUTOMATA',
  branch: 'main',
  lastSession: '2 hours ago',
}

export default function WorkspaceRestoreScreen() {
  const [isRunning, setIsRunning] = useState(false)
  const [statuses, setStatuses] = useState<Record<string, StepStatus>>(
    Object.fromEntries(STEPS.map(s => [s.id, 'pending']))
  )
  const [currentStep, setCurrentStep] = useState(-1)
  const [aiReason, setAiReason] = useState('')
  const [done, setDone] = useState(false)

  const AI_REASONS = [
    'Loading context from last session 2h ago…',
    'Found 3 open TODOs and 1 incomplete feature branch…',
    'Restoring to commit "feat: vector retrieval pipeline"…',
    'Preparing dev environment based on your stack…',
    'All systems restored. Ready to code.',
  ]

  const startRestore = async () => {
    setIsRunning(true)
    setDone(false)
    setStatuses(Object.fromEntries(STEPS.map(s => [s.id, 'pending'])))

    for (let i = 0; i < STEPS.length; i++) {
      const step = STEPS[i]
      setCurrentStep(i)
      setAiReason(AI_REASONS[i] ?? '')
      setStatuses(prev => ({ ...prev, [step.id]: 'running' }))
      await new Promise(r => setTimeout(r, step.duration))
      setStatuses(prev => ({ ...prev, [step.id]: 'done' }))
    }

    setAiReason(AI_REASONS[STEPS.length] ?? '')
    setCurrentStep(-1)
    setIsRunning(false)
    setDone(true)
  }

  const completedCount = Object.values(statuses).filter(s => s === 'done').length
  const progress = (completedCount / STEPS.length) * 100

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
          <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', marginBottom: '0.25rem', fontFamily: 'var(--font-mono)' }}>{DEMO_PROJECT.path}</div>
          <h2 style={{ fontSize: '1.4rem', fontFamily: 'var(--font-display)', marginBottom: '0.4rem' }}>{DEMO_PROJECT.name}</h2>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--info)', fontFamily: 'var(--font-mono)' }}>⎇ {DEMO_PROJECT.branch}</span>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>Last session: {DEMO_PROJECT.lastSession}</span>
          </div>
        </div>
        <motion.button
          onClick={startRestore}
          disabled={isRunning}
          whileHover={!isRunning ? { scale: 1.04, boxShadow: '0 0 30px rgba(108,79,255,0.4)' } : undefined}
          whileTap={!isRunning ? { scale: 0.97 } : undefined}
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
            cursor: isRunning ? 'not-allowed' : 'pointer',
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

      {/* Progress bar */}
      <AnimatePresence>
        {(isRunning || done) && (
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
              <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{completedCount}/{STEPS.length} steps</span>
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
              background: 'var(--success-muted)',
              border: '1px solid rgba(16,185,129,0.25)',
              borderRadius: 'var(--r-md)',
            }}
          >
            <Sparkles size={16} color="var(--success)" />
            <span style={{ fontSize: '0.85rem', color: 'var(--success)', fontWeight: 500 }}>
              Workspace fully restored. You're ready to continue where you left off.
            </span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Steps */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
        {STEPS.map((step, i) => {
          const status = statuses[step.id]
          const Icon = step.icon
          const isCurrentStep = currentStep === i
          return (
            <motion.div
              key={step.id}
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.04, type: 'spring', stiffness: 280, damping: 26 }}
            >
              <GlassCard
                padding="1rem"
                style={{
                  borderLeft: `3px solid ${status === 'done' ? step.color : status === 'running' ? step.color : 'var(--border-soft)'}`,
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
                      background: status === 'done' ? step.color + '20' : status === 'running' ? step.color + '15' : 'var(--bg-elevated)',
                      border: `1.5px solid ${status === 'done' || status === 'running' ? step.color : 'var(--border-soft)'}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      flexShrink: 0,
                      boxShadow: isCurrentStep ? `0 0 16px ${step.color}50` : 'none',
                      transition: 'all var(--dur-base) var(--ease-in-out)',
                    }}
                  >
                    <span style={{ color: status === 'done' || status === 'running' ? step.color : 'var(--text-tertiary)', display: 'flex' }}><Icon size={17} strokeWidth={2} /></span>
                  </motion.div>

                  {/* Content */}
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '0.85rem', fontWeight: 600, color: status === 'pending' && !isRunning ? 'var(--text-tertiary)' : 'var(--text-primary)', marginBottom: '0.15rem' }}>
                      {step.label}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{step.description}</div>
                  </div>

                  {/* Status icon */}
                  <div style={{ flexShrink: 0 }}>
                    {status === 'done' && (
                      <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 500, damping: 20 }}>
                        <CheckCircle2 size={20} color={step.color} />
                      </motion.div>
                    )}
                    {status === 'running' && (
                      <Loader2 size={18} style={{ animation: 'spin 1s linear infinite', color: step.color }} />
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
