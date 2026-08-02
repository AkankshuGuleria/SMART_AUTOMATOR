/**
 * components/ui/ProgressRing.tsx
 * Animated SVG circular progress with gradient stroke and glow.
 */
import { useEffect, useRef } from 'react'
import { motion, useMotionValue, useTransform, animate } from 'framer-motion'

interface ProgressRingProps {
  value: number        // 0–100
  size?: number
  stroke?: number
  label?: string
  sublabel?: string
  color?: string
  glow?: boolean
  gradient?: [string, string]
  animate?: boolean
}

export default function ProgressRing({
  value,
  size = 80,
  stroke = 6,
  label,
  sublabel,
  color = 'var(--accent)',
  glow = false,
  gradient,
  animate: shouldAnimate = true,
}: ProgressRingProps) {
  const idRef = useRef(`pr-${Math.random().toString(36).slice(2)}`)
  const id = idRef.current
  const r = (size - stroke) / 2
  const circ = 2 * Math.PI * r
  const motionVal = useMotionValue(0)
  const dashoffset = useTransform(motionVal, (v) => circ - (v / 100) * circ)

  useEffect(() => {
    if (shouldAnimate) {
      const ctrl = animate(motionVal, value, {
        duration: 1.2,
        ease: [0.16, 1, 0.3, 1],
        delay: 0.1,
      })
      return () => ctrl.stop()
    } else {
      motionVal.set(value)
    }
  }, [value, shouldAnimate, motionVal])

  return (
    <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: 'rotate(-90deg)', overflow: 'visible' }}>
        {gradient && (
          <defs>
            <linearGradient id={`${id}-grad`} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor={gradient[0]} />
              <stop offset="100%" stopColor={gradient[1]} />
            </linearGradient>
          </defs>
        )}
        {/* Track */}
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none"
          stroke="var(--border-soft)"
          strokeWidth={stroke}
        />
        {/* Progress */}
        <motion.circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none"
          stroke={gradient ? `url(#${id}-grad)` : color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circ}
          style={{
            strokeDashoffset: dashoffset,
            filter: glow ? `drop-shadow(0 0 6px ${color})` : undefined,
          }}
        />
      </svg>
      {/* Center label */}
      {(label || sublabel) && (
        <div style={{
          position: 'absolute',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          lineHeight: 1.2,
        }}>
          {label && (
            <span style={{
              fontSize: size < 70 ? '0.75rem' : '1rem',
              fontWeight: 700,
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-display)',
            }}>
              {label}
            </span>
          )}
          {sublabel && (
            <span style={{
              fontSize: size < 70 ? '0.55rem' : '0.65rem',
              color: 'var(--text-tertiary)',
              marginTop: 1,
            }}>
              {sublabel}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
