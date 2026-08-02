/**
 * components/ui/VariantHelpers.ts
 * Typed Framer Motion variant helpers to avoid 'type: string' TS errors.
 */
import type { Variants, Transition } from 'framer-motion'

export const springTransition = (stiffness = 220, damping = 24): Transition => ({
  type: 'spring' as const,
  stiffness,
  damping,
})

export function staggerContainer(delay = 0.07, delayChildren = 0): Variants {
  return {
    hidden: {},
    show: { transition: { staggerChildren: delay, delayChildren } },
  }
}

export function fadeUpItem(stiffness = 220, damping = 24, delay = 0): Variants {
  return {
    hidden: { opacity: 0, y: 20 },
    show: {
      opacity: 1,
      y: 0,
      transition: { type: 'spring' as const, stiffness, damping, delay },
    },
  }
}

export const defaultItem: Variants = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: 'spring' as const, stiffness: 220, damping: 24 },
  },
}

export const defaultContainer: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07 } },
}
