/**
 * components/ui/AIStatusBadge.tsx
 * Animated AI status indicator: thinking, active, idle states with orbital ring.
 */
import { motion, AnimatePresence } from 'framer-motion'

type AIState = 'idle' | 'thinking' | 'active' | 'offline'

interface AIStatusBadgeProps {
  state: AIState
  label?: string
  size?: 'sm' | 'md' | 'lg'
}

const stateConfig: Record<AIState, { color: string; glow: string; label: string }> = {
  idle:     { color: 'var(--success)',  glow: 'var(--success-glow)',  label: 'Idle' },
  thinking: { color: 'var(--ai-cyan)',  glow: 'var(--ai-cyan-glow)',  label: 'Thinking…' },
  active:   { color: 'var(--accent)',   glow: 'var(--accent-glow)',   label: 'Active' },
  offline:  { color: 'var(--error)',    glow: 'rgba(0,0,0,0)',        label: 'Offline' },
}

const sizeMap = { sm: 8, md: 12, lg: 16 }
const orbitSizeMap = { sm: 16, md: 24, lg: 32 }

export default function AIStatusBadge({ state, label, size = 'md' }: AIStatusBadgeProps) {
  const cfg = stateConfig[state]
  const dotSize = sizeMap[size]
  const orbitSize = orbitSizeMap[size]

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
      <div style={{ position: 'relative', width: orbitSize, height: orbitSize, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {/* Pulse ring */}
        <AnimatePresence>
          {state !== 'offline' && (
            <motion.span
              key={`ring-${state}`}
              initial={{ scale: 1, opacity: 0.7 }}
              animate={{ scale: 1.8, opacity: 0 }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'easeOut' }}
              style={{
                position: 'absolute',
                width: dotSize, height: dotSize,
                borderRadius: '50%',
                background: cfg.color,
                pointerEvents: 'none',
              }}
            />
          )}
        </AnimatePresence>

        {/* Orbit dot (thinking only) */}
        {state === 'thinking' && (
          <motion.span
            animate={{ rotate: 360 }}
            transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
            style={{
              position: 'absolute',
              width: orbitSize, height: orbitSize,
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'center',
            }}
          >
            <span style={{
              width: dotSize * 0.5,
              height: dotSize * 0.5,
              borderRadius: '50%',
              background: 'var(--ai-cyan)',
              boxShadow: '0 0 8px var(--ai-cyan)',
              marginTop: 0,
            }} />
          </motion.span>
        )}

        {/* Core dot */}
        <motion.span
          animate={state === 'active' ? { scale: [1, 1.1, 1] } : { scale: 1 }}
          transition={{ duration: 1.5, repeat: state === 'active' ? Infinity : 0 }}
          style={{
            width: dotSize,
            height: dotSize,
            borderRadius: '50%',
            background: cfg.color,
            boxShadow: `0 0 ${dotSize}px ${cfg.glow}`,
            flexShrink: 0,
            zIndex: 1,
          }}
        />
      </div>

      {label !== undefined && (
        <span style={{ fontSize: '0.75rem', color: cfg.color, fontWeight: 500 }}>
          {label ?? cfg.label}
        </span>
      )}
    </div>
  )
}
