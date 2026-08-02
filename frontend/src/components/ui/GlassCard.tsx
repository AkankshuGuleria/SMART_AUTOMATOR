/**
 * components/ui/GlassCard.tsx
 * Premium glass card with cursor-reactive glow, hover elevation, and optional gradient border.
 */
import { useRef, useState, type ReactNode, type CSSProperties } from 'react'
import { motion } from 'framer-motion'

interface GlassCardProps {
  children: ReactNode
  className?: string
  style?: CSSProperties
  hoverable?: boolean
  glowing?: boolean
  gradient?: boolean
  onClick?: () => void
  padding?: string | number
}

export default function GlassCard({
  children,
  className = '',
  style,
  hoverable = true,
  glowing = false,
  gradient = false,
  onClick,
  padding = '1.25rem',
}: GlassCardProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [glow, setGlow] = useState({ x: 0, y: 0, opacity: 0 })

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!hoverable) return
    const rect = ref.current?.getBoundingClientRect()
    if (!rect) return
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    setGlow({ x, y, opacity: 1 })
  }

  const handleMouseLeave = () => setGlow((g) => ({ ...g, opacity: 0 }))

  return (
    <motion.div
      ref={ref}
      className={`glass-card-root ${className}`}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onClick={onClick}
      whileHover={hoverable ? { y: -3, transition: { type: 'spring', stiffness: 300, damping: 30 } } : undefined}
      style={{
        position: 'relative',
        background: 'var(--bg-glass)',
        backdropFilter: 'var(--blur-md)',
        WebkitBackdropFilter: 'var(--blur-md)',
        border: '1px solid var(--border-glass)',
        borderRadius: 'var(--r-lg)',
        padding,
        overflow: 'hidden',
        cursor: onClick ? 'pointer' : undefined,
        transition: 'box-shadow var(--dur-base) var(--ease-out), border-color var(--dur-base) var(--ease-out)',
        boxShadow: glowing ? 'var(--shadow-glow)' : undefined,
        ...style,
      }}
    >
      {/* Gradient border overlay */}
      {gradient && (
        <span
          style={{
            position: 'absolute',
            inset: -1,
            borderRadius: 'calc(var(--r-lg) + 1px)',
            background: 'linear-gradient(135deg, rgba(108,79,255,0.6) 0%, transparent 40%, rgba(34,211,238,0.4) 100%)',
            pointerEvents: 'none',
            opacity: 0,
            transition: 'opacity var(--dur-base) var(--ease-in-out)',
          }}
          className="gradient-border-overlay"
        />
      )}

      {/* Cursor-reactive glow */}
      {hoverable && (
        <span
          style={{
            position: 'absolute',
            width: 200,
            height: 200,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(108,79,255,0.12) 0%, transparent 70%)',
            pointerEvents: 'none',
            left: glow.x - 100,
            top: glow.y - 100,
            opacity: glow.opacity,
            transition: 'opacity 0.3s ease',
            zIndex: 0,
          }}
        />
      )}

      {/* Content */}
      <div style={{ position: 'relative', zIndex: 1 }}>
        {children}
      </div>
    </motion.div>
  )
}
