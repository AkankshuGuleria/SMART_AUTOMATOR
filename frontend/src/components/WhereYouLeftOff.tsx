/**
 * components/WhereYouLeftOff.tsx — latest session snapshot + one-click resume.
 */
import { useState } from 'react'
import { withPermission } from '../lib/permissions'
import { History, GitBranch, FileCode, Play, Loader2, Save, CheckCircle2, XCircle, MinusCircle, Server, ListChecks } from 'lucide-react'
import GlassCard from './ui/GlassCard'
import { usePolling } from '../lib/usePolling'
import { getLatestSnapshot, resumeWorkspace, takeSnapshot, type Snapshot, type ResumeResult } from '../lib/api'

function ago(ts: number): string {
  const s = Math.max(0, Date.now() / 1000 - ts)
  if (s < 90) return 'just now'
  if (s < 3600) return `${Math.round(s / 60)} min ago`
  if (s < 86400) return `${Math.round(s / 3600)} h ago`
  return `${Math.round(s / 86400)} days ago`
}

const REASON: Record<string, string> = { idle: 'when you went idle', periodic: 'automatically', shutdown: 'when AUTOMATA closed', manual: 'manually' }

export default function WhereYouLeftOff({ projectId, onOpenTasks }: { projectId?: string; onOpenTasks?: () => void }) {
  const [snap, setSnap] = useState<Snapshot | null | undefined>(undefined)
  const [busy, setBusy] = useState<'resume' | 'save' | null>(null)
  const [result, setResult] = useState<ResumeResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  usePolling(async () => {
    if (!projectId) return
    setSnap((await getLatestSnapshot(projectId)).snapshot)
  }, 60000, [projectId], !!projectId)

  if (!projectId) return null
  const d = snap?.data

  const save = async () => {
    setBusy('save'); setError(null)
    try { await takeSnapshot(projectId); setSnap((await getLatestSnapshot(projectId)).snapshot) } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save')
    } finally { setBusy(null) }
  }
  const resume = async () => {
    setBusy('resume'); setError(null); setResult(null)
    try {
      const r = await withPermission(pid => resumeWorkspace(projectId, {}, pid))
      if (r.denied) setError('Cancelled — nothing was opened.')
      else setResult(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Resume failed')
    } finally { setBusy(null) }
  }

  return (
    <GlassCard hoverable={false} glowing>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <History size={15} color="var(--accent-2)" />
          <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>Where you left off</span>
          {snap && <span style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)' }}>saved {ago(snap.created_at)} {REASON[snap.reason] ?? ''}</span>}
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button onClick={save} disabled={!!busy} style={ghost}>{busy === 'save' ? <Loader2 size={12} className="spin" /> : <Save size={12} />} Save now</button>
          <button onClick={resume} disabled={!!busy || !snap} style={primary(!!busy || !snap)}>
            {busy === 'resume' ? <Loader2 size={12} className="spin" /> : <Play size={12} />} Resume workspace
          </button>
        </div>
      </div>

      {snap === undefined && <div style={muted}>Loading…</div>}
      {snap === null && <div style={muted}>No snapshot yet. AUTOMATA saves one every 10 minutes, when you go idle and when it closes — or press “Save now”.</div>}
      {d && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12, fontSize: '0.78rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            {d.branch && <Row icon={GitBranch} text={<>Branch <b>{d.branch}</b>{d.changed_files.length ? ` · ${d.changed_files.length} uncommitted` : ' · clean'}</>} />}
            {d.last_commit && <Row icon={GitBranch} text={<span style={{ fontFamily: 'var(--font-mono)' }}>{d.last_commit}</span>} />}
            {d.dev_servers.length > 0 && <Row icon={Server} text={`Dev servers: ${d.dev_servers.map(s => s.port).join(', ')}`} />}
            {d.current_task && (
              <button onClick={onOpenTasks} style={{ ...ghost, justifyContent: 'flex-start', width: 'fit-content' }}>
                <ListChecks size={12} /> Task: {d.current_task.title} ({d.current_task.progress})
              </button>
            )}
          </div>
          <div>
            <div style={label}>Recent files</div>
            {d.recent_files.length === 0 && <div style={muted}>None recorded yet</div>}
            {d.recent_files.slice(0, 5).map(f => (
              <div key={f} title={f} style={{ display: 'flex', gap: 5, alignItems: 'center', color: 'var(--text-secondary)', overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>
                <FileCode size={11} style={{ flexShrink: 0 }} /> {f.split(/[\\/]/).slice(-2).join('/')}
              </div>
            ))}
          </div>
          {d.open_todos.length > 0 && (
            <div>
              <div style={label}>Open TODOs</div>
              {d.open_todos.slice(0, 4).map((t, i) => <div key={i} style={{ color: 'var(--text-secondary)' }}>• {t.replace(/^TODO \([^)]*\):\s*/, '')}</div>)}
            </div>
          )}
        </div>
      )}
      {error && <div style={{ fontSize: '0.74rem', color: 'var(--error)', marginTop: 8 }}>{error}</div>}
      {result && (
        <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 3 }}>
          {result.error && <div style={{ fontSize: '0.75rem', color: 'var(--error)' }}>{result.error}</div>}
          {result.steps.map((s, i) => (
            <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
              {s.status === 'ok' ? <CheckCircle2 size={12} color="var(--success)" /> : s.status === 'skipped' ? <MinusCircle size={12} color="var(--text-tertiary)" /> : <XCircle size={12} color="var(--error)" />}
              <b style={{ textTransform: 'capitalize' }}>{s.step.replace('_', ' ')}</b> {s.detail}
            </div>
          ))}
        </div>
      )}
    </GlassCard>
  )
}

function Row({ icon: Icon, text }: { icon: typeof History; text: React.ReactNode }) {
  return <div style={{ display: 'flex', gap: 6, alignItems: 'center', color: 'var(--text-secondary)' }}><Icon size={12} style={{ flexShrink: 0 }} /> {text}</div>
}

const muted: React.CSSProperties = { fontSize: '0.78rem', color: 'var(--text-tertiary)' }
const label: React.CSSProperties = { fontSize: '0.64rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600, marginBottom: 4 }
const ghost: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 4, padding: '0.3rem 0.65rem', borderRadius: 'var(--r-sm)',
  border: '1px solid var(--border-soft)', background: 'var(--bg-elevated)', color: 'var(--text-secondary)',
  fontSize: '0.72rem', cursor: 'pointer', fontFamily: 'var(--font-sans)',
}
function primary(disabled: boolean): React.CSSProperties {
  return {
    display: 'flex', alignItems: 'center', gap: 4, padding: '0.3rem 0.75rem', borderRadius: 'var(--r-sm)', border: 'none',
    background: disabled ? 'var(--bg-hover)' : 'var(--accent)', color: disabled ? 'var(--text-disabled)' : '#fff',
    fontSize: '0.72rem', fontWeight: 600, cursor: disabled ? 'not-allowed' : 'pointer', fontFamily: 'var(--font-sans)',
  }
}
