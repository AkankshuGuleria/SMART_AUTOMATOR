/**
 * components/PermissionsSettings.tsx — what AUTOMATA may do without asking.
 * Every category starts at "Ask every time".
 */
import { useEffect, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import GlassCard from './ui/GlassCard'
import { getPermissions, setPermission, type PermissionPolicy } from '../lib/permissions'

export default function PermissionsSettings() {
  const [items, setItems] = useState<PermissionPolicy[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getPermissions().then(r => setItems(r.permissions)).catch(e => setError(e instanceof Error ? e.message : 'Unavailable'))
  }, [])

  const change = async (category: string, mode: 'ask' | 'allow') => {
    setError(null)
    try {
      await setPermission(category, mode)
      setItems(prev => prev?.map(p => (p.category === category ? { ...p, mode } : p)) ?? null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save')
    }
  }

  return (
    <GlassCard hoverable={false}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
        <ShieldCheck size={16} color="var(--success)" />
        <h3 style={{ color: 'var(--text-primary)', fontSize: '0.9rem' }}>Permissions</h3>
      </div>
      <p style={{ fontSize: '0.76rem', color: 'var(--text-tertiary)', marginBottom: '0.9rem' }}>
        AUTOMATA asks before it controls your PC. Choose what it may do without asking.
      </p>
      {error && <div style={{ fontSize: '0.75rem', color: 'var(--error)', marginBottom: 8 }}>{error}</div>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {items?.map(p => (
          <div key={p.category} style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--text-primary)' }}>{p.label}</div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginTop: 2 }}>{p.help}</div>
            </div>
            <div role="radiogroup" aria-label={p.label} style={{ display: 'flex', borderRadius: 8, border: '1px solid var(--border-soft)', overflow: 'hidden', flexShrink: 0 }}>
              {(['ask', 'allow'] as const).map(mode => (
                <button key={mode} role="radio" aria-checked={p.mode === mode} onClick={() => change(p.category, mode)} style={{
                  padding: '0.32rem 0.7rem', border: 'none', cursor: 'pointer', fontSize: '0.72rem', fontFamily: 'var(--font-sans)',
                  background: p.mode === mode ? (mode === 'allow' ? 'var(--warning-muted)' : 'var(--accent-muted)') : 'transparent',
                  color: p.mode === mode ? (mode === 'allow' ? 'var(--warning)' : 'var(--accent-2)') : 'var(--text-tertiary)',
                }}>{mode === 'ask' ? 'Ask every time' : 'Always allow'}</button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </GlassCard>
  )
}
