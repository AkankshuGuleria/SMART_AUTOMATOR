/**
 * components/PermissionHost.tsx — the "Allow AUTOMATA to …?" prompt.
 * Mounted once per window (main app and work bar); lib/permissions.ts drives it.
 */
import { useEffect, useRef, useState } from 'react'
import { ShieldQuestion, Check, X, ShieldCheck } from 'lucide-react'
import { setPermissionListener, type PermissionDecision, type PermissionRequest } from '../lib/permissions'

interface Pending { req: PermissionRequest; resolve: (d: PermissionDecision) => void }

export default function PermissionHost({ compact = false }: { compact?: boolean }) {
  const [queue, setQueue] = useState<Pending[]>([])
  const allowRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    setPermissionListener((req, resolve) => setQueue(q => [...q, { req, resolve }]))
    return () => setPermissionListener(null)
  }, [])

  const current = queue[0]
  useEffect(() => { if (current) allowRef.current?.focus() }, [current])

  const answer = (d: PermissionDecision) => {
    if (!current) return
    current.resolve(d)
    setQueue(q => q.slice(1))
  }

  useEffect(() => {
    if (!current) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); answer('deny') } }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  })

  if (!current) return null
  const { req } = current
  return (
    <div role="presentation" style={{
      position: 'fixed', inset: 0, zIndex: 1000, display: 'flex', alignItems: compact ? 'flex-end' : 'center',
      justifyContent: 'center', background: 'rgba(5,5,10,0.55)', padding: compact ? 12 : 24,
    }}>
      <div role="alertdialog" aria-modal="true" aria-labelledby="perm-title" aria-describedby="perm-action" style={{
        width: '100%', maxWidth: 440, borderRadius: 16, padding: 18, background: 'var(--bg-elevated, #16161f)',
        border: '1px solid rgba(124,92,255,0.35)', boxShadow: '0 20px 60px rgba(0,0,0,0.5)', color: 'var(--text-primary)',
        fontFamily: 'var(--font-sans)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <ShieldQuestion size={18} color="var(--accent-2)" />
          <span id="perm-title" style={{ fontWeight: 700, fontSize: '0.92rem' }}>Allow AUTOMATA to {req.label.toLowerCase()}?</span>
        </div>
        <div id="perm-action" style={{ fontSize: '0.86rem', color: 'var(--text-primary)', marginBottom: 6, lineHeight: 1.5 }}>{req.action}</div>
        <div style={{ fontSize: '0.74rem', color: 'var(--text-tertiary)', marginBottom: 14 }}>{req.help}</div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <button onClick={() => answer('deny')} style={btn}><X size={13} /> Deny</button>
          <button onClick={() => answer('always')} style={btn} title={`Don't ask again for: ${req.label}`}>
            <ShieldCheck size={13} /> Always allow
          </button>
          <button ref={allowRef} onClick={() => answer('once')} style={{ ...btn, background: 'var(--accent)', borderColor: 'var(--accent)', color: '#fff' }}>
            <Check size={13} /> Allow once
          </button>
        </div>
        <div style={{ fontSize: '0.66rem', color: 'var(--text-tertiary)', marginTop: 10 }}>
          Change what AUTOMATA may do without asking in Settings → Permissions.
        </div>
      </div>
    </div>
  )
}

const btn: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 5, padding: '0.45rem 0.85rem', borderRadius: 8,
  border: '1px solid var(--border-soft, #333)', background: 'transparent', color: 'var(--text-secondary)',
  fontSize: '0.78rem', cursor: 'pointer', fontFamily: 'var(--font-sans)',
}
