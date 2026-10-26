/**
 * screens/SetupScreen.tsx
 * Self-check of everything AUTOMATA depends on, and local (offline) AI setup.
 */
import { useState } from 'react'
import { ShieldCheck, CheckCircle2, AlertTriangle, Info, XCircle, Cpu, Download, Loader2, Wifi, WifiOff, RefreshCw } from 'lucide-react'
import GlassCard from '../components/ui/GlassCard'
import { usePolling } from '../lib/usePolling'
import {
  getSelfCheck, getAiStatus, getLocalRecommendation, getPullStatus, pullLocalModel, selectLocalModel, installOllama,
  type SelfCheckItem, type AiStatus, type LocalRecommendation, type PullStatus,
} from '../lib/api'

function LevelIcon({ item }: { item: SelfCheckItem }) {
  if (item.ok) return <CheckCircle2 size={16} color="var(--success)" />
  if (item.level === 'error') return <XCircle size={16} color="var(--error)" />
  if (item.level === 'warning') return <AlertTriangle size={16} color="var(--warning)" />
  return <Info size={16} color="var(--text-tertiary)" />
}

export default function SetupScreen() {
  const [checks, setChecks] = useState<SelfCheckItem[] | null>(null)
  const [ai, setAi] = useState<AiStatus | null>(null)
  const [rec, setRec] = useState<LocalRecommendation | null>(null)
  const [pull, setPull] = useState<PullStatus | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  const loadChecks = async () => setChecks((await getSelfCheck()).checks)
  usePolling(loadChecks, 30000)
  usePolling(async () => {
    const [a, r] = await Promise.all([getAiStatus(), rec ? Promise.resolve(rec) : getLocalRecommendation()])
    setAi(a); setRec(r)
  }, 10000)
  usePolling(async () => setPull(await getPullStatus()), pull?.status === 'pulling' ? 1000 : 8000)

  const run = async (key: string, fn: () => Promise<{ success?: boolean; error?: string; detail?: string }>) => {
    setBusy(key); setMsg(null)
    try {
      const res = await fn()
      setMsg(res.success === false ? (res.error ?? 'Failed') : (res.detail ?? 'Done'))
      setAi(await getAiStatus())
    } catch (e) { setMsg(e instanceof Error ? e.message : 'Failed') } finally { setBusy(null) }
  }

  const ollama = ai?.ollama
  const models = rec?.catalog ?? []

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.1rem', maxWidth: 940 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ marginBottom: 4, display: 'flex', alignItems: 'center', gap: 10 }}><ShieldCheck size={22} /> Setup & health</h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>What AUTOMATA needs to run in the background, remember your work and keep working offline.</p>
        </div>
        <button onClick={loadChecks} style={ghost}><RefreshCw size={13} /> Re-check</button>
      </div>

      <GlassCard hoverable={false} padding="1rem">
        {!checks && <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>Checking…</div>}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {checks?.map(c => (
            <div key={c.key} style={{ display: 'flex', gap: 10, padding: '0.55rem 0', borderBottom: '1px solid var(--border-soft)' }}>
              <LevelIcon item={c} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: '0.82rem' }}>
                  <span style={{ fontWeight: 600 }}>{c.label}</span>
                  <span style={{ color: 'var(--text-tertiary)', textAlign: 'right' }}>{c.detail}</span>
                </div>
                {c.fix && <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginTop: 2 }}>{c.fix}</div>}
              </div>
            </div>
          ))}
        </div>
      </GlassCard>

      <GlassCard hoverable={false} padding="1rem">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, gap: 8, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Cpu size={16} color="var(--ai-cyan)" />
            <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Local AI (works offline)</span>
          </div>
          {ai && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', color: ai.online ? 'var(--success)' : 'var(--warning)' }}>
              {ai.online ? <Wifi size={13} /> : <WifiOff size={13} />}
              {ai.online ? 'Online' : 'Offline — local model only'}
              {ai.last_answer.provider && <span style={{ color: 'var(--text-tertiary)' }}> · last answer: {ai.last_answer.provider}{ai.last_answer.model ? ` (${ai.last_answer.model})` : ''}</span>}
            </span>
          )}
        </div>

        {rec && (
          <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: 8 }}>
            Recommended for this PC: <b>{rec.chat_model}</b> — {rec.reason}. Needs ≈{rec.needed_gb} GB, {rec.free_gb ?? '?'} GB free in <code>{rec.models_dir}</code>.
            {rec.warning && <div style={{ color: 'var(--warning)', marginTop: 4 }}>{rec.warning}</div>}
          </div>
        )}

        {ollama && !ollama.installed && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Ollama is not installed.</span>
            <button onClick={() => run('install', installOllama)} disabled={busy === 'install'} style={primary(busy === 'install')}>
              {busy === 'install' ? <Loader2 size={13} className="spin" /> : <Download size={13} />} Install Ollama (opens installer)
            </button>
            <a href="https://ollama.com/download" target="_blank" rel="noreferrer" style={{ fontSize: '0.74rem', color: 'var(--ai-cyan)' }}>or download manually</a>
          </div>
        )}
        {ollama && ollama.installed && !ollama.running && (
          <div style={{ fontSize: '0.8rem', color: 'var(--warning)' }}>Ollama is installed but not running — start “Ollama” from the Start menu.</div>
        )}

        {ollama?.running && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6 }}>
            {models.map(m => {
              const pulled = ollama.models.some(x => x === m.name || x === `${m.name}:latest`)
              const selected = m.use === 'chat' && ollama.chat_model === m.name
              const pulling = pull?.status === 'pulling' && pull.model === m.name
              return (
                <div key={m.name} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '0.5rem 0.6rem', borderRadius: 'var(--r-sm)', background: 'var(--bg-elevated)', border: `1px solid ${selected ? 'var(--accent)' : 'var(--border-soft)'}` }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 600 }}>{m.name} {m.name === rec?.chat_model && <span style={{ color: 'var(--success)', fontWeight: 400, fontSize: '0.7rem' }}>· recommended</span>}</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{m.label} · {m.size_gb} GB · {m.use}</div>
                    {pulling && (
                      <div style={{ height: 4, background: 'var(--bg-hover)', borderRadius: 99, marginTop: 6, overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${pull?.percent ?? 0}%`, background: 'var(--accent)', transition: 'width 0.4s' }} />
                      </div>
                    )}
                  </div>
                  {!pulled && !pulling && (
                    <button onClick={() => run(`pull-${m.name}`, () => pullLocalModel(m.name))} disabled={pull?.status === 'pulling'} style={ghost}>
                      <Download size={12} /> Download
                    </button>
                  )}
                  {pulling && <span style={{ fontSize: '0.72rem', color: 'var(--ai-cyan)' }}>{pull?.percent ?? 0}%</span>}
                  {pulled && m.use === 'chat' && !selected && (
                    <button onClick={() => run(`sel-${m.name}`, () => selectLocalModel(m.name))} style={ghost}>Use</button>
                  )}
                  {pulled && (selected || m.use !== 'chat') && <CheckCircle2 size={15} color="var(--success)" />}
                </div>
              )
            })}
            {pull?.status === 'error' && <div style={{ fontSize: '0.74rem', color: 'var(--error)' }}>Download failed: {pull.error}</div>}
          </div>
        )}
        {msg && <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: 8 }}>{msg}</div>}
        {ai && (
          <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginTop: 10 }}>
            Cloud providers configured: {Object.entries(ai.cloud_providers).filter(([, v]) => v).map(([k]) => k).join(', ') || 'none'}.
            Memory search always works offline (keyword search); semantic search turns on when an embedding model is available.
          </div>
        )}
      </GlassCard>
    </div>
  )
}

const ghost: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 5, padding: '0.35rem 0.7rem', borderRadius: 'var(--r-sm)',
  border: '1px solid var(--border-soft)', background: 'var(--bg-elevated)', color: 'var(--text-secondary)',
  fontSize: '0.74rem', cursor: 'pointer', fontFamily: 'var(--font-sans)',
}
function primary(disabled: boolean): React.CSSProperties {
  return {
    display: 'flex', alignItems: 'center', gap: 5, padding: '0.45rem 0.85rem', borderRadius: 'var(--r-sm)', border: 'none',
    background: disabled ? 'var(--bg-hover)' : 'var(--accent)', color: disabled ? 'var(--text-disabled)' : '#fff',
    fontSize: '0.76rem', fontWeight: 600, cursor: disabled ? 'not-allowed' : 'pointer', fontFamily: 'var(--font-sans)',
  }
}
