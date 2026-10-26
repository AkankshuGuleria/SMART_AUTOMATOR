/**
 * components/WorkBarSettings.tsx — Settings card for the AI work bar:
 * see the shortcut, record a new one, reset it, or open the bar now.
 */
import { useEffect, useState } from 'react'
import { Keyboard, PanelTop, RotateCcw, Check, AlertTriangle } from 'lucide-react'
import GlassCard from './ui/GlassCard'
import {
  isTauri, getWorkbarShortcut, setWorkbarShortcut, toggleWorkbar, shortcutFromEvent, RESERVED_SHORTCUTS,
  type WorkbarShortcut,
} from '../lib/desktop'

const DEFAULT = 'Alt+Space'

function Keys({ combo }: { combo: string }) {
  return (
    <span style={{ display: 'inline-flex', gap: 4 }}>
      {combo.split('+').map(k => (
        <kbd key={k} style={{
          padding: '2px 8px', borderRadius: 6, border: '1px solid var(--border-soft)', borderBottomWidth: 2,
          background: 'var(--bg-elevated)', fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: 'var(--text-primary)',
        }}>{k}</kbd>
      ))}
    </span>
  )
}

export default function WorkBarSettings() {
  const desktop = isTauri()
  const [status, setStatus] = useState<WorkbarShortcut | null>(null)
  const [recording, setRecording] = useState(false)
  const [pending, setPending] = useState<string | null>(null)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => { getWorkbarShortcut().then(setStatus) }, [])

  useEffect(() => {
    if (!recording) return
    const onKey = (e: KeyboardEvent) => {
      e.preventDefault(); e.stopPropagation()
      if (e.key === 'Escape' && !e.ctrlKey && !e.altKey && !e.shiftKey) { setRecording(false); setPending(null); return }
      const combo = shortcutFromEvent(e)
      if (combo) setPending(combo)
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [recording])

  const apply = async (combo: string) => {
    setMessage(null)
    if (RESERVED_SHORTCUTS[combo]) {
      setMessage({ ok: false, text: `${combo} is not allowed: ${RESERVED_SHORTCUTS[combo]}. Pick another combination.` })
      setPending(null)
      setRecording(false)
      return
    }
    try {
      const s = await setWorkbarShortcut(combo)
      setStatus(s)
      setMessage({ ok: true, text: `Saved. Press ${s.shortcut} from any app.` })
    } catch (e) {
      setMessage({ ok: false, text: e instanceof Error ? e.message : String(e) })
    } finally {
      setRecording(false); setPending(null)
    }
  }

  return (
    <GlassCard hoverable={false}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
        <PanelTop size={16} color="var(--accent-2)" />
        <h3 style={{ color: 'var(--text-primary)', fontSize: '0.9rem' }}>AI work bar</h3>
      </div>
      <p style={{ fontSize: '0.76rem', color: 'var(--text-tertiary)', marginBottom: '0.9rem' }}>
        A bar over any app: ask, command, play music, search, or read your screen. Esc or clicking elsewhere hides it.
      </p>

      {!desktop ? (
        <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>Shortcut settings are available in the AUTOMATA desktop app.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', flexWrap: 'wrap' }}>
            <Keyboard size={15} color="var(--text-tertiary)" />
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>Shortcut</span>
            {recording
              ? <span style={{ fontSize: '0.8rem', color: 'var(--accent-2)' }}>{pending ? <Keys combo={pending} /> : 'Press the new key combination… (Esc to cancel)'}</span>
              : status && <Keys combo={status.shortcut} />}
            {status && !recording && (status.registered
              ? <span style={{ fontSize: '0.72rem', color: 'var(--success)', display: 'flex', alignItems: 'center', gap: 4 }}><Check size={12} /> active</span>
              : <span style={{ fontSize: '0.72rem', color: 'var(--warning)', display: 'flex', alignItems: 'center', gap: 4 }}><AlertTriangle size={12} /> not active — {status.error ?? 'in use by another app'}</span>)}
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {!recording && <button onClick={() => { setRecording(true); setMessage(null) }} style={btn}>Change shortcut</button>}
            {recording && pending && <button onClick={() => apply(pending)} style={{ ...btn, background: 'var(--accent)', color: '#fff', borderColor: 'var(--accent)' }}>Save {pending}</button>}
            {recording && <button onClick={() => { setRecording(false); setPending(null) }} style={btn}>Cancel</button>}
            {!recording && status?.shortcut !== DEFAULT && <button onClick={() => apply(DEFAULT)} style={btn}><RotateCcw size={12} /> Reset to {DEFAULT}</button>}
            <button onClick={() => toggleWorkbar()} style={btn}><PanelTop size={12} /> Open work bar now</button>
          </div>
          {message && <div style={{ fontSize: '0.76rem', color: message.ok ? 'var(--success)' : 'var(--warning)' }}>{message.text}</div>}
          <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
            Use a combination other apps don't need — e.g. Ctrl+Alt+A is taken by Kilo Code, Ctrl+Shift+Space by editors.
          </div>
        </div>
      )}
    </GlassCard>
  )
}

const btn: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 5, padding: '0.4rem 0.8rem', borderRadius: 'var(--r-sm)',
  border: '1px solid var(--border-soft)', background: 'var(--bg-elevated)', color: 'var(--text-secondary)',
  fontSize: '0.76rem', cursor: 'pointer', fontFamily: 'var(--font-sans)',
}
