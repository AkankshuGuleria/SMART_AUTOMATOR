/**
 * CompanionApp.tsx — the AI work bar (Alt+Space or Ctrl+Alt+A, like a game bar).
 *
 * One box for everything: ask about the project, give commands ("play lofi on
 * spotify", "search tauri tray on github", "using antigravity add a contact
 * form"), plus tiles for media, reading the screen (only when pressed) and the
 * things you do when switching back into work. Esc or clicking elsewhere hides it.
 */
import { useEffect, useRef, useState } from 'react'
import {
  Zap, Send, Loader2, History, Save, Maximize2, Wifi, WifiOff, Search, ScanText,
  Play, Pause, SkipBack, SkipForward, Volume1, Volume2, Music2, ListChecks,
} from 'lucide-react'
import {
  runAssist, resumeWorkspace, takeSnapshot, getAiStatus, getNowPlaying, mediaControl, readScreen, listTasks,
  type NowPlaying,
} from './lib/api'
import { hideCurrentWindow, openMainScreen, showMainWindow } from './lib/desktop'
import { usePolling } from './lib/usePolling'

const ACTIVE_PROJECT_KEY = 'automata.activeProjectId'

function activeProject(): string | undefined {
  try { return localStorage.getItem(ACTIVE_PROJECT_KEY) ?? undefined } catch { return undefined }
}

const EXAMPLES = [
  'play lofi beats on spotify', 'what did I work on yesterday?', "what's on my screen?",
  'search tauri global shortcut on github', 'using antigravity add a contact form',
]

export default function CompanionApp() {
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [reply, setReply] = useState<{ text: string; ok: boolean } | null>(null)
  const [online, setOnline] = useState<boolean | null>(null)
  const [music, setMusic] = useState<NowPlaying | null>(null)
  const [waitingTasks, setWaitingTasks] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'dark')
    inputRef.current?.focus()
    const onFocus = () => { inputRef.current?.focus(); inputRef.current?.select() }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') hideCurrentWindow() }
    window.addEventListener('focus', onFocus)
    window.addEventListener('keydown', onKey)
    getAiStatus().then(s => setOnline(s.online)).catch(() => setOnline(null))
    return () => { window.removeEventListener('focus', onFocus); window.removeEventListener('keydown', onKey) }
  }, [])

  usePolling(async () => { setMusic(await getNowPlaying()) }, 4000, [])
  usePolling(async () => {
    const { tasks } = await listTasks(activeProject())
    setWaitingTasks(tasks.filter(t => t.status === 'waiting_input' || t.status === 'waiting_approval').length)
  }, 8000, [])

  const run = async (label: string, fn: () => Promise<{ text: string; ok: boolean }>) => {
    setBusy(label); setReply(null)
    try { setReply(await fn()) } catch (e) {
      setReply({ ok: false, text: e instanceof TypeError ? 'AUTOMATA agent is not running.' : (e instanceof Error ? e.message : 'Failed') })
    } finally { setBusy(null) }
  }

  const send = (text = input.trim()) => {
    if (!text) return
    setInput('')
    run('send', async () => {
      const res = await runAssist(text, activeProject())
      return { ok: res.success, text: res.reply || 'Done.' }
    })
  }

  const media = (action: Parameters<typeof mediaControl>[0]) => run('media', async () => {
    const r = await mediaControl(action)
    if (r.now_playing) setMusic(r.now_playing)
    else setMusic(await getNowPlaying())
    return { ok: r.success, text: r.message ?? r.error ?? '' }
  })

  const pid = activeProject()
  const playing = !!music?.playing

  return (
    <div style={shell}>
      <div style={panel}>
        {/* header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={logo}><Zap size={12} color="#fff" /></span>
            <span style={{ fontWeight: 700, fontSize: '0.78rem', letterSpacing: '0.1em' }}>AUTOMATA</span>
            <span style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)' }}>work bar</span>
            {online !== null && (online ? <Wifi size={12} color="var(--success)" /> : <WifiOff size={12} color="var(--warning)" />)}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: '0.66rem', color: 'var(--text-tertiary)' }}>Esc to hide</span>
            <button onClick={showMainWindow} title="Open the full app" aria-label="Open the full app" style={iconBtn}><Maximize2 size={14} /></button>
          </div>
        </div>

        {/* command box */}
        <div style={commandBox}>
          <Zap size={16} color="var(--accent-2)" style={{ flexShrink: 0 }} />
          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') send() }}
            placeholder="Ask, command or search…"
            aria-label="Ask, command or search"
            style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: 'var(--text-primary)', fontSize: '0.98rem', fontFamily: 'var(--font-sans)' }}
          />
          <button onClick={() => send()} disabled={!!busy || !input.trim()} aria-label="Send" style={{ ...iconBtn, width: 34, height: 34, borderRadius: 10, background: input.trim() ? 'var(--accent)' : 'transparent', color: input.trim() ? '#fff' : 'var(--text-tertiary)' }}>
            {busy === 'send' ? <Loader2 size={15} className="spin" /> : <Send size={15} />}
          </button>
        </div>

        {/* reply */}
        <div style={{ minHeight: 0, flex: 1, overflowY: 'auto', margin: '10px 0' }}>
          {busy && busy !== 'media' && !reply && (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', display: 'flex', gap: 8, alignItems: 'center' }}>
              <Loader2 size={13} className="spin" /> {busy === 'screen' ? 'Reading the window behind this bar…' : 'Working…'}
            </div>
          )}
          {reply && (
            <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.82rem', lineHeight: 1.55, color: reply.ok ? 'var(--text-secondary)' : 'var(--warning)' }}>{reply.text}</div>
          )}
          {!reply && !busy && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {EXAMPLES.map(x => <button key={x} onClick={() => send(x)} style={chip}>{x}</button>)}
            </div>
          )}
        </div>

        {/* tiles */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr', gap: 8 }}>
          <div style={tile}>
            <div style={tileLabel}><Music2 size={11} /> Now playing</div>
            <div style={{ fontSize: '0.78rem', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {music?.title ?? 'Nothing playing'}
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', minHeight: 14 }}>
              {music?.artist ?? (music?.title ? '' : 'Try “play … on spotify”')}
            </div>
            <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
              <button onClick={() => media('previous')} aria-label="Previous track" style={mediaBtn}><SkipBack size={14} /></button>
              <button onClick={() => media('play_pause')} aria-label={playing ? 'Pause' : 'Play'} style={{ ...mediaBtn, background: 'var(--accent)', color: '#fff' }}>
                {playing ? <Pause size={14} /> : <Play size={14} />}
              </button>
              <button onClick={() => media('next')} aria-label="Next track" style={mediaBtn}><SkipForward size={14} /></button>
              <span style={{ flex: 1 }} />
              <button onClick={() => media('volume_down')} aria-label="Volume down" style={mediaBtn}><Volume1 size={14} /></button>
              <button onClick={() => media('volume_up')} aria-label="Volume up" style={mediaBtn}><Volume2 size={14} /></button>
            </div>
          </div>

          <button
            onClick={() => run('screen', async () => {
              const q = input.trim(); setInput('')
              const r = await readScreen(q || undefined)
              return r.success ? { ok: true, text: `${r.answer}\n\n— read from: ${r.window?.title ?? 'window'}` } : { ok: false, text: r.error ?? 'Could not read the screen.' }
            })}
            disabled={!!busy}
            style={{ ...tile, cursor: 'pointer', textAlign: 'left', fontFamily: 'var(--font-sans)', color: 'var(--text-primary)', display: 'flex', flexDirection: 'column', justifyContent: 'flex-start' }}
          >
            <div style={tileLabel}><ScanText size={11} /> Screen</div>
            <div style={{ fontSize: '0.8rem', fontWeight: 600 }}>{busy === 'screen' ? 'Reading…' : 'Read my screen'}</div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', marginTop: 2 }}>
              Explains the window behind this bar. Type a question first to ask something specific. Only runs when pressed.
            </div>
          </button>

          <div style={{ ...tile, display: 'flex', flexDirection: 'column', gap: 5 }}>
            <div style={tileLabel}>Quick</div>
            <button disabled={!input.trim() || !!busy} onClick={() => send(`search ${input.trim()}`)} style={quickBtn}><Search size={12} /> Search the web</button>
            <button disabled={!pid || !!busy} onClick={() => run('resume', async () => {
              const r = await resumeWorkspace(pid!)
              return { ok: !r.error, text: r.error ?? r.steps.map(s => `${s.status === 'ok' ? '✓' : s.status === 'skipped' ? '–' : '✗'} ${s.step}: ${s.detail}`).join('\n') }
            })} style={quickBtn}><History size={12} /> Resume work</button>
            <button disabled={!pid || !!busy} onClick={() => run('save', async () => { await takeSnapshot(pid!); return { ok: true, text: 'Saved where you left off.' } })} style={quickBtn}><Save size={12} /> Save state</button>
            <button onClick={() => openMainScreen('tasks')} style={{ ...quickBtn, color: waitingTasks ? 'var(--warning)' : quickBtn.color }}>
              <ListChecks size={12} /> {waitingTasks ? `${waitingTasks} task${waitingTasks > 1 ? 's' : ''} need you` : 'Tasks'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

const shell: React.CSSProperties = { height: '100dvh', width: '100vw', padding: 10, boxSizing: 'border-box', background: 'transparent', fontFamily: 'var(--font-sans)', color: 'var(--text-primary)' }
const panel: React.CSSProperties = {
  height: '100%', display: 'flex', flexDirection: 'column', padding: 16, boxSizing: 'border-box',
  borderRadius: 18, background: 'rgba(14, 14, 22, 0.985)', border: '1px solid rgba(255,255,255,0.09)',
  boxShadow: '0 18px 50px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.05)', backdropFilter: 'blur(24px)',
}
const logo: React.CSSProperties = { width: 22, height: 22, borderRadius: 6, background: 'linear-gradient(135deg, var(--accent), var(--ai-cyan))', display: 'flex', alignItems: 'center', justifyContent: 'center' }
const commandBox: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 10, padding: '6px 6px 6px 14px', borderRadius: 14, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(124,92,255,0.35)' }
const iconBtn: React.CSSProperties = { display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer' }
const chip: React.CSSProperties = { padding: '0.28rem 0.65rem', borderRadius: 999, border: '1px solid var(--border-soft)', background: 'transparent', color: 'var(--text-secondary)', fontSize: '0.72rem', cursor: 'pointer', fontFamily: 'var(--font-sans)' }
const tile: React.CSSProperties = { padding: '10px 12px', borderRadius: 12, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)', minWidth: 0 }
const tileLabel: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 5, fontSize: '0.6rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-tertiary)', fontWeight: 600, marginBottom: 4 }
const mediaBtn: React.CSSProperties = { ...iconBtn, width: 28, height: 28, borderRadius: 8, background: 'rgba(255,255,255,0.06)', color: 'var(--text-secondary)' }
const quickBtn: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 6, padding: '4px 6px', borderRadius: 7, border: 'none', background: 'rgba(255,255,255,0.04)', color: 'var(--text-secondary)', fontSize: '0.72rem', cursor: 'pointer', fontFamily: 'var(--font-sans)', textAlign: 'left' }
