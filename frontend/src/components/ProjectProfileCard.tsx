/**
 * components/ProjectProfileCard.tsx — what this project is, detected from its files:
 * stack, how to run it, missing env vars, and project-specific module readiness.
 */
import { useState } from 'react'
import { Layers, Terminal, KeyRound, RefreshCw, Loader2, Boxes } from 'lucide-react'
import GlassCard from './ui/GlassCard'
import { usePolling } from '../lib/usePolling'
import { getProjectProfile, type ProjectProfile } from '../lib/api'

export default function ProjectProfileCard({ projectId, compact = false, onOpenInbox }: { projectId?: string; compact?: boolean; onOpenInbox?: () => void }) {
  const [profile, setProfile] = useState<ProjectProfile | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const load = async (refresh = false) => {
    if (!projectId) return
    try { setProfile(await getProjectProfile(projectId, refresh)); setError(null) } catch (e) {
      setError(e instanceof Error ? e.message : 'Profile unavailable')
    }
  }
  usePolling(() => load(false), 120000, [projectId], !!projectId)
  if (!projectId) return null

  const refresh = async () => { setRefreshing(true); await load(true); setRefreshing(false) }
  const missing = profile?.env.missing ?? []
  const chips = profile ? [...profile.frameworks.slice(0, 8), ...profile.databases, ...profile.infrastructure.slice(0, 2)] : []

  return (
    <GlassCard hoverable={false}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Layers size={15} color="var(--ai-cyan)" />
          <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>Project profile</span>
          {profile && <span style={{ fontSize: '0.66rem', color: 'var(--text-tertiary)' }}>{profile.file_count} files · scanned in {profile.scan_ms} ms</span>}
        </div>
        <button onClick={refresh} disabled={refreshing} title="Rescan the project" style={iconBtn}>
          {refreshing ? <Loader2 size={13} className="spin" /> : <RefreshCw size={13} />}
        </button>
      </div>
      {error && <div style={{ fontSize: '0.78rem', color: 'var(--error)' }}>{error}</div>}
      {!profile && !error && <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>Reading the project…</div>}
      {profile && (
        <>
          {profile.type && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)' }}>{profile.type.label}</span>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>because {profile.type.reasons.join('; ')}</span>
              </div>
              {profile.type.focus.length > 0 && (
                <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginTop: 3 }}>
                  What matters here: {profile.type.focus.join(' · ')}
                </div>
              )}
            </div>
          )}
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 8 }}>{profile.summary}</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginBottom: 10 }}>
            {chips.map(c => <span key={c} style={chip}>{c}</span>)}
            {profile.languages.slice(0, 3).map(l => <span key={l.name} style={{ ...chip, color: 'var(--text-tertiary)' }}>{l.name} {l.percent}%</span>)}
          </div>

          {!compact && profile.run_book.length > 0 && (
            <div style={{ marginBottom: 10 }}>
              <div style={label}><Terminal size={11} /> How to run</div>
              {profile.run_book.map(r => (
                <div key={r.path} style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginBottom: 2 }}>
                  <b>{r.path === '.' ? 'root' : r.path}</b>: {Object.entries(r.commands).filter(([k]) => ['install', 'dev', 'test', 'build'].includes(k)).map(([k, v]) => (
                    <span key={k} style={{ marginRight: 8 }}>{k} <code style={code}>{v}</code></span>
                  ))}
                </div>
              ))}
              {profile.ports.length > 0 && <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>Ports: {profile.ports.join(', ')}</div>}
            </div>
          )}

          {missing.length > 0 && (
            <button onClick={onOpenInbox} style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%', textAlign: 'left', marginBottom: 10, padding: '0.5rem 0.65rem', borderRadius: 'var(--r-sm)', border: '1px solid rgba(245,158,11,0.3)', background: 'var(--warning-muted)', color: 'var(--warning)', fontSize: '0.75rem', cursor: onOpenInbox ? 'pointer' : 'default', fontFamily: 'var(--font-sans)' }}>
              <KeyRound size={13} /> {missing.length} env var{missing.length === 1 ? '' : 's'} not set: {missing.slice(0, 5).join(', ')}{missing.length > 5 ? '…' : ''}
            </button>
          )}

          <div style={label}><Boxes size={11} /> Modules (from this project's structure)</div>
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(auto-fill, minmax(${compact ? 150 : 200}px, 1fr))`, gap: 8 }}>
            {profile.modules.slice(0, compact ? 6 : 14).map(m => (
              <div key={m.path} title={m.basis} style={{ padding: '0.5rem 0.6rem', borderRadius: 'var(--r-sm)', background: 'var(--bg-elevated)', border: '1px solid var(--border-soft)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem', marginBottom: 4, gap: 6 }}>
                  <span style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.name}</span>
                  <span style={{ color: m.pct >= 70 ? 'var(--success)' : m.pct >= 45 ? 'var(--warning)' : 'var(--error)', fontWeight: 600 }}>{m.pct}%</span>
                </div>
                <div style={{ height: 3, background: 'var(--bg-hover)', borderRadius: 99, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${m.pct}%`, background: m.pct >= 70 ? 'var(--success)' : m.pct >= 45 ? 'var(--warning)' : 'var(--error)' }} />
                </div>
                <div style={{ fontSize: '0.64rem', color: 'var(--text-tertiary)', marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.path} · {m.basis}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </GlassCard>
  )
}

const chip: React.CSSProperties = { fontSize: '0.68rem', padding: '2px 7px', borderRadius: 'var(--r-full)', background: 'var(--accent-muted)', color: 'var(--accent-2)' }
const label: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 5, fontSize: '0.64rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600, marginBottom: 5 }
const code: React.CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: '0.7rem', background: 'var(--bg-elevated)', padding: '0 4px', borderRadius: 3 }
const iconBtn: React.CSSProperties = { background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', display: 'flex' }
