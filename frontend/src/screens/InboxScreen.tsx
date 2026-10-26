/**
 * screens/InboxScreen.tsx
 * "Needs from you": API keys, connection strings, accounts and manual steps,
 * each with instructions. Values go to Windows Credential Manager and/or the
 * project's .env — AUTOMATA never stores them itself.
 */
import { useState } from 'react'
import { Inbox, KeyRound, Database, ExternalLink, RefreshCw, Check, Loader2, EyeOff, Eye, ShieldAlert } from 'lucide-react'
import GlassCard from '../components/ui/GlassCard'
import { usePolling } from '../lib/usePolling'
import { listNeeds, resolveNeed, type NeedItem } from '../lib/api'

const KIND_LABEL: Record<string, string> = {
  api_key: 'API key', connection_string: 'Connection string', secret: 'Secret', config: 'Setting',
}

function NeedCard({ need, onDone }: { need: NeedItem; onDone: () => void }) {
  const [value, setValue] = useState('')
  const [show, setShow] = useState(false)
  const [saveTo, setSaveTo] = useState<'both' | 'keyring' | 'env_file'>('both')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ tone: 'ok' | 'error' | 'warn'; text: string } | null>(null)

  const submit = async (mode: 'keyring' | 'env_file' | 'both' | 'done' | 'dismiss') => {
    setBusy(true); setMsg(null)
    try {
      const res = await resolveNeed(need.id, mode, mode === 'done' || mode === 'dismiss' ? undefined : value)
      setValue('')
      if (res.warnings?.length) setMsg({ tone: 'warn', text: res.warnings.join(' ') })
      else setMsg({ tone: 'ok', text: res.saved_to?.length ? `Saved to ${res.saved_to.join(' and ')}` : 'Marked as handled' })
      setTimeout(onDone, res.warnings?.length ? 2500 : 600)
    } catch (e) {
      setMsg({ tone: 'error', text: e instanceof Error ? e.message : 'Could not save' })
    } finally { setBusy(false) }
  }

  const Icon = need.kind === 'connection_string' ? Database : KeyRound
  return (
    <GlassCard hoverable={false} padding="1rem">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
        <Icon size={15} color="var(--warning)" />
        <code style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>{need.var}</code>
        <span style={badge}>{KIND_LABEL[need.kind] ?? need.kind}</span>
        {need.provider && <span style={{ ...badge, color: 'var(--accent-2)' }}>{need.provider}</span>}
      </div>
      <ol style={{ margin: '4px 0 8px 18px', padding: 0, fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        {need.steps.map((s, i) => <li key={i}>{s}</li>)}
      </ol>
      {need.docs_url && (
        <a href={need.docs_url} target="_blank" rel="noreferrer" style={{ fontSize: '0.74rem', color: 'var(--ai-cyan)', display: 'inline-flex', gap: 4, alignItems: 'center' }}>
          Open {need.provider ?? 'docs'} <ExternalLink size={11} />
        </a>
      )}
      <div style={{ display: 'flex', gap: 6, marginTop: 10, alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <input
            type={show ? 'text' : 'password'}
            value={value}
            onChange={e => setValue(e.target.value)}
            placeholder={`Paste ${need.var}`}
            autoComplete="off"
            spellCheck={false}
            style={{
              width: '100%', boxSizing: 'border-box', padding: '0.5rem 2rem 0.5rem 0.6rem', borderRadius: 'var(--r-sm)',
              border: '1px solid var(--border-soft)', background: 'var(--bg-elevated)', color: 'var(--text-primary)',
              fontFamily: 'var(--font-mono)', fontSize: '0.78rem', outline: 'none',
            }}
          />
          <button onClick={() => setShow(v => !v)} aria-label={show ? 'Hide value' : 'Show value'} style={{ position: 'absolute', right: 6, top: 6, background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)' }}>
            {show ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        </div>
        <select value={saveTo} onChange={e => setSaveTo(e.target.value as typeof saveTo)} style={select}>
          <option value="both">Credential Manager + .env</option>
          <option value="keyring">Credential Manager only</option>
          <option value="env_file">.env only</option>
        </select>
        <button disabled={busy || !value.trim()} onClick={() => submit(saveTo)} style={primary(busy || !value.trim())}>
          {busy ? <Loader2 size={13} className="spin" /> : <Check size={13} />} Save
        </button>
      </div>
      {need.target_file && saveTo !== 'keyring' && (
        <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>→ {need.target_file}</div>
      )}
      <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
        <button onClick={() => submit('done')} disabled={busy} style={link}>I set it up myself</button>
        <button onClick={() => submit('dismiss')} disabled={busy} style={link}>Not needed</button>
      </div>
      {msg && (
        <div style={{ fontSize: '0.74rem', marginTop: 6, color: msg.tone === 'ok' ? 'var(--success)' : msg.tone === 'warn' ? 'var(--warning)' : 'var(--error)' }}>
          {msg.text}
        </div>
      )}
    </GlassCard>
  )
}

export default function InboxScreen({ projectId }: { projectId?: string }) {
  const [needs, setNeeds] = useState<NeedItem[] | null>(null)
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = async (refresh = false) => {
    try {
      setNeeds((await listNeeds(projectId, refresh)).needs)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load the inbox')
    }
  }
  usePolling(() => load(false), 15000, [projectId])

  const rescan = async () => { setScanning(true); await load(true); setScanning(false) }

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: 900 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ marginBottom: 4, display: 'flex', alignItems: 'center', gap: 10 }}><Inbox size={22} /> Needs from you</h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
            Keys, connection strings and accounts your project needs. Values are saved to Windows Credential Manager or the project's .env — never to AUTOMATA's memory.
          </p>
        </div>
        <button onClick={rescan} disabled={!projectId || scanning} style={{ ...link, display: 'flex', gap: 5, alignItems: 'center', border: '1px solid var(--border-soft)', padding: '0.4rem 0.8rem', borderRadius: 'var(--r-sm)' }}>
          {scanning ? <Loader2 size={13} className="spin" /> : <RefreshCw size={13} />} Rescan project
        </button>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.74rem', color: 'var(--text-tertiary)' }}>
        <ShieldAlert size={13} /> Paste values only from the official provider dashboard. Never share production secrets with an AI app.
      </div>
      {error && <div style={{ color: 'var(--error)', fontSize: '0.8rem' }}>{error}</div>}
      {needs === null && !error && <div style={{ color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>Loading…</div>}
      {needs && needs.length === 0 && (
        <GlassCard hoverable={false}>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Nothing needed right now. {projectId ? 'Use “Rescan project” after adding features that need new keys.' : 'Select a project to scan it.'}
          </div>
        </GlassCard>
      )}
      {needs?.map(n => <NeedCard key={n.id} need={n} onDone={() => load(false)} />)}
    </div>
  )
}

const badge: React.CSSProperties = {
  fontSize: '0.64rem', padding: '1px 6px', borderRadius: 4, background: 'var(--bg-elevated)',
  color: 'var(--text-tertiary)', border: '1px solid var(--border-soft)',
}
const select: React.CSSProperties = {
  padding: '0.45rem', borderRadius: 'var(--r-sm)', border: '1px solid var(--border-soft)',
  background: 'var(--bg-elevated)', color: 'var(--text-secondary)', fontSize: '0.74rem', fontFamily: 'var(--font-sans)',
}
const link: React.CSSProperties = {
  background: 'none', border: 'none', color: 'var(--text-tertiary)', fontSize: '0.74rem', cursor: 'pointer',
  fontFamily: 'var(--font-sans)', padding: 0,
}
function primary(disabled: boolean): React.CSSProperties {
  return {
    display: 'flex', alignItems: 'center', gap: 4, padding: '0.45rem 0.8rem', borderRadius: 'var(--r-sm)', border: 'none',
    background: disabled ? 'var(--bg-hover)' : 'var(--accent)', color: disabled ? 'var(--text-disabled)' : '#fff',
    fontSize: '0.76rem', fontWeight: 600, cursor: disabled ? 'not-allowed' : 'pointer', fontFamily: 'var(--font-sans)',
  }
}
