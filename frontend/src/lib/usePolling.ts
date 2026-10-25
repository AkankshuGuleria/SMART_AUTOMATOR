/**
 * lib/usePolling.ts — visibility-aware polling hook.
 *
 * - Runs `fn` immediately, then every `intervalMs`.
 * - Skips ticks while the window is hidden and refreshes as soon as it is
 *   visible again, so a minimised app costs no network or CPU.
 * - Never overlaps requests: a slow response delays the next tick.
 */
import { useEffect, useRef } from 'react'

export function usePolling(
  fn: () => Promise<unknown> | void,
  intervalMs: number,
  deps: ReadonlyArray<unknown> = [],
  enabled = true,
): void {
  const fnRef = useRef(fn)
  fnRef.current = fn

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    let timer: number | undefined
    let inFlight = false

    const tick = async () => {
      if (cancelled || inFlight) return
      if (typeof document !== 'undefined' && document.hidden) {
        schedule()
        return
      }
      inFlight = true
      try {
        await fnRef.current()
      } catch {
        // callers own their error state; polling keeps going
      } finally {
        inFlight = false
        schedule()
      }
    }

    const schedule = () => {
      if (cancelled) return
      window.clearTimeout(timer)
      timer = window.setTimeout(tick, intervalMs)
    }

    const onVisible = () => {
      if (!document.hidden) {
        window.clearTimeout(timer)
        tick()
      }
    }

    tick()
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, enabled, ...deps])
}
