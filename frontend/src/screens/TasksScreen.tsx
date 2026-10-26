/**
 * screens/TasksScreen.tsx
 * Delegated agent tasks: create, follow each step live, approve gated steps.
 */
import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ListChecks, Play, X, Check, Loader2, Clock, AlertTriangle, ShieldCheck,
  ChevronDown, ChevronRight, FileCode, KeyRound, Sparkles, Ban, MessageCircleQuestion, FolderOpen,
} from 'lucide-react'
import GlassCard from '../components/ui/GlassCard'
import { usePolling } from '../lib/usePolling'
import {
  listTasks, getTask, createTask, approveTask, cancelTask, answerTask,
  type TaskSummary, type TaskDetail, type TaskStep, type TaskQuestion,
} from '../lib/api'

const AGENTS = [
  { id: 'antigravity', label: 'Antigravity', hint: 'Opens the project and its agent chat' },
  { id: 'kilo', label: 'Kilo Code', hint: 'Kilo Code agent inside Antigravity IDE' },
  { id: 'claude', label: 'Claude', hint: 'Claude Code CLI, or the Claude app' },
  { id: 'vscode', label: 'VS Code', hint: 'VS Code agent chat' },
  { id: 'chatgpt', label: 'ChatGPT', hint: 'ChatGPT in your browser (no file access)' },
  { id: 'cursor', label: 'Cursor', hint: 'cursor-agent CLI, or the Cursor chat panel' },
]

const STATUS_STYLE: Record<string, { color: string; label: string }> = {
  planned: { color: 'var(--text-tertiary)', label: 'Planned' },
  running: { color: 'var(--ai-cyan)', label: 'Running' },
  waiting_approval: { color: 'var(--warning)', label: 'Needs your approval' },
  waiting_input: { color: 'var(--ai-cyan)', label: 'Needs your answers' },
  paused: { color: 'var(--warning)', label: 'Paused' },
  done: { color: 'var(--success)', label: 'Done' },
  failed: { color: 'var(--error)', label: 'Failed' },
  cancelled: { color: 'var(--text-tertiary)', label: 'Cancelled' },
}

function ago(ts: number): string {
  const s = Math.max(0, Date.now() / 1000 - ts)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

function StepIcon({ status }: { status: string }) {
  const size = 14
  if (status === 'done') return <Check size={size} color="var(--success)" />
  if (status === 'running') return <Loader2 size={size} color="var(--ai-cyan)" className="spin" />
  if (status === 'waiting_approval') return <ShieldCheck size={size} color="var(--warning)" />
  if (status === 'waiting_input') return <MessageCircleQuestion size={size} color="var(--ai-cyan)" />
  if (status === 'failed') return <AlertTriangle size={size} color="var(--error)" />
  if (status === 'skipped') return <Ban size={size} color="var(--text-tertiary)" />
  return <Clock size={size} color="var(--text-tertiary)" />
}

function StepOutput({ step }: { step: TaskStep }) {
  const out = step.output as Record<string, unknown> | null
  if (!out) return null
  if (step.kind === 'prompt' && typeof out.prompt === 'string') {
    return (
      <pre style={preStyle}>{out.prompt}</pre>
    )
  }
  if (step.kind === 'watch' && Array.isArray(out.changed_files) && out.changed_files.length) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginTop: 6 }}>
        {(out.changed_files as string[]).slice(0, 30).map(f => (
          <span key={f} style={{ fontSize: '0.72rem', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', display: 'flex', gap: 6, alignItems: 'center' }}>
            <FileCode size={11} /> {f}
          </span>
        ))}
      </div>
    )
  }
  if (step.kind === 'verify' && Array.isArray(out.results)) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6 }}>
        {(out.results as Array<Record<string, string | number>>).map((r, i) => (
          <div key={i}>
            <div style={{ fontSize: '0.74rem', color: r.status === 'ok' ? 'var(--success)' : 'var(--error)' }}>
              {r.status === 'ok' ? '✓' : '✗'} <code>{r.command}</code> in {r.path}
            </div>
            {r.status !== 'ok' && <pre style={preStyle}>{String(r.output_tail || '')}</pre>}
          </div>
        ))}
      </div>
    )
  }
  return null
}

function QuestionsForm({ questions, busy, onSubmit }: {
  questions: TaskQuestion[]; busy: boolean; onSubmit: (answers: Record<string, string>) => void
}) {
  const [values, setValues] = useState<Record<string, string>>(
    () => Object.fromEntries(questions.map(q => [q.id, q.default ?? ''])),
  )
  const set = (id: string, v: string) => setValues(prev => ({ ...prev, [id]: v }))
  return (
    <div style={{ marginTop: 12, padding: '0.85rem', borderRadius: 'var(--r-md)', border: '1px solid rgba(34,211,238,0.3)', background: 'rgba(34,211,238,0.06)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, fontSize: '0.82rem', color: 'var(--ai-cyan)', marginBottom: 10 }}>
        <MessageCircleQuestion size={14} /> A few questions before the hand-off
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {questions.map(q => (
          <label key={q.id} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
              {q.kind === 'folder' && <FolderOpen size={13} />} {q.question}
              {q.from_model && <span style={{ fontSize: '0.62rem', color: 'var(--text-tertiary)' }}>suggested by AI</span>}
            </span>
            {q.kind === 'choice' && q.options ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {q.options.map(o => (
                  <button type="button" key={o} onClick={() => set(q.id, o)} style={{
                    ...chip, borderColor: values[q.id] === o ? 'var(--accent)' : 'var(--border-soft)',
                    background: values[q.id] === o ? 'var(--accent-muted)' : 'transparent',
                    color: values[q.id] === o ? 'var(--accent-2)' : 'var(--text-secondary)',
                  }}>{o}</button>
                ))}
              </div>
            ) : q.kind === 'folder' ? (
              <input value={values[q.id] ?? ''} onChange={e => set(q.id, e.target.value)} style={{ ...field, fontFamily: 'var(--font-mono)' }} />
            ) : (
              <textarea value={values[q.id] ?? ''} onChange={e => set(q.id, e.target.value)} rows={2} placeholder="Optional" style={{ ...field, resize: 'vertical' }} />
            )}
            {q.help && <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{q.help}</span>}
          </label>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
        <button disabled={busy} onClick={() => onSubmit({})} style={ghostBtn}>Use defaults</button>
        <button disabled={busy} onClick={() => onSubmit(values)} style={primaryBtn(busy)}>
          {busy ? <Loader2 size={13} className="spin" /> : <Check size={13} />} Continue
        </button>
      </div>
    </div>
  )
}

function NewTaskForm({ projectId, onCreated }: { projectId?: string; onCreated: (t: TaskDetail) => void }) {
  const [agent, setAgent] = useState('antigravity')
  const [request, setRequest] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const submit = async () => {
    if (!request.trim()) return
    setBusy(true); setError(null)
    try {
      const res = await createTask(request.trim(), agent, projectId)
      setRequest('')
      onCreated(res.task)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create the task')
    } finally { setBusy(false) }
  }
  return (
    <GlassCard hoverable={false} padding="1rem">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <Sparkles size={15} color="var(--accent-2)" />
        <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>Delegate a task</span>
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
        {AGENTS.map(a => (
          <button key={a.id} title={a.hint} onClick={() => setAgent(a.id)} style={{
            ...chip, borderColor: agent === a.id ? 'var(--accent)' : 'var(--border-soft)',
            background: agent === a.id ? 'var(--accent-muted)' : 'transparent',
            color: agent === a.id ? 'var(--accent-2)' : 'var(--text-secondary)',
          }}>{a.label}</button>
        ))}
      </div>
      <textarea
        value={request}
        onChange={e => setRequest(e.target.value)}
        placeholder="e.g. Create a landing page with pricing, sign-up and Stripe checkout"
        rows={3}
        style={{
          width: '100%', resize: 'vertical', padding: '0.6rem 0.75rem', borderRadius: 'var(--r-md)',
          border: '1px solid var(--border-soft)', background: 'var(--bg-elevated)', color: 'var(--text-primary)',
          fontFamily: 'var(--font-sans)', fontSize: '0.84rem', outline: 'none', boxSizing: 'border-box',
        }}
      />
      {!projectId && <div style={{ fontSize: '0.72rem', color: 'var(--warning)', marginTop: 6 }}>No project selected — the agent won't get project context.</div>}
      {error && <div style={{ fontSize: '0.75rem', color: 'var(--error)', marginTop: 6 }}>{error}</div>}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
        <button onClick={submit} disabled={busy || !request.trim()} style={primaryBtn(busy || !request.trim())}>
          {busy ? <Loader2 size={13} className="spin" /> : <Play size={13} />} Plan task
        </button>
      </div>
      <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginTop: 6 }}>
        AUTOMATA writes the prompt from your project's stack and memory, then waits for your approval before sending it or running builds.
      </div>
    </GlassCard>
  )
}

export default function TasksScreen({ projectId, onOpenInbox }: { projectId?: string; onOpenInbox?: () => void }) {
  const [tasks, setTasks] = useState<TaskSummary[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [detail, setDetail] = useState<TaskDetail | null>(null)
  const [open, setOpen] = useState<Record<number, boolean>>({})
  const [acting, setActing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  usePolling(async () => {
    const res = await listTasks(projectId)
    setTasks(res.tasks)
    if (!selected && res.tasks.length) setSelected(res.tasks[0].id)
  }, 5000, [projectId])

  const active = detail && ['running', 'planned'].includes(detail.status)
  usePolling(async () => {
    if (selected) setDetail((await getTask(selected)).task)
  }, active ? 1500 : 6000, [selected, active], !!selected)

  const act = async (fn: () => Promise<unknown>) => {
    setActing(true); setError(null)
    try { await fn(); if (selected) setDetail((await getTask(selected)).task) } catch (e) {
      setError(e instanceof Error ? e.message : 'Action failed')
    } finally { setActing(false) }
  }

  const waitingStep = useMemo(() => detail?.steps.find(s => s.status === 'waiting_approval'), [detail])
  const questionStep = useMemo(() => detail?.steps.find(s => s.status === 'waiting_input'), [detail])
  const questions = ((questionStep?.output as { questions?: TaskQuestion[] } | null)?.questions) ?? []

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div>
        <h1 style={{ marginBottom: 4, display: 'flex', alignItems: 'center', gap: 10 }}><ListChecks size={22} /> Tasks</h1>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
          Multi-step work handed to Antigravity, Claude, VS Code or ChatGPT — with your approval at every risky step.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, 340px) minmax(0, 1fr)', gap: '1rem', alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <NewTaskForm projectId={projectId} onCreated={t => { setSelected(t.id); setDetail(t); setTasks(prev => [t, ...prev]) }} />
          {tasks.length === 0 && (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', padding: '0.5rem' }}>
              No tasks yet. Try “using antigravity create a landing page” in chat, or use the form above.
            </div>
          )}
          {tasks.map(t => {
            const st = STATUS_STYLE[t.status] ?? STATUS_STYLE.planned
            return (
              <button key={t.id} onClick={() => setSelected(t.id)} style={{
                textAlign: 'left', padding: '0.7rem 0.8rem', borderRadius: 'var(--r-md)', cursor: 'pointer',
                border: `1px solid ${selected === t.id ? 'var(--accent)' : 'var(--border-soft)'}`,
                background: selected === t.id ? 'var(--accent-muted)' : 'var(--bg-elevated)', color: 'var(--text-primary)',
                fontFamily: 'var(--font-sans)',
              }}>
                <div style={{ fontSize: '0.82rem', fontWeight: 600, marginBottom: 3 }}>{t.title}</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: 'var(--text-tertiary)' }}>
                  <span style={{ color: st.color }}>● {st.label}</span>
                  <span>{t.agent} · {t.steps_done ?? 0}/{t.steps_total ?? 0} · {ago(t.updated_at)}</span>
                </div>
              </button>
            )
          })}
        </div>

        <div>
          {!detail ? (
            <GlassCard hoverable={false}><div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>Select a task.</div></GlassCard>
          ) : (
            <GlassCard hoverable={false} padding="1.1rem">
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                <div style={{ minWidth: 0 }}>
                  <h2 style={{ fontSize: '1.05rem', margin: 0 }}>{detail.title}</h2>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: 3 }}>“{detail.request}”</div>
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                  {(detail.status === 'waiting_approval' || detail.status === 'paused') && (
                    <button disabled={acting} onClick={() => act(() => approveTask(detail.id))} style={primaryBtn(acting)}>
                      <Check size={13} /> {detail.status === 'paused' ? 'Resume' : `Approve: ${waitingStep?.title ?? 'next step'}`}
                    </button>
                  )}
                  {!['done', 'failed', 'cancelled'].includes(detail.status) && (
                    <button disabled={acting} onClick={() => act(() => cancelTask(detail.id))} style={ghostBtn}>
                      <X size={13} /> Cancel
                    </button>
                  )}
                </div>
              </div>
              {error && <div style={{ fontSize: '0.75rem', color: 'var(--error)', marginTop: 8 }}>{error}</div>}
              {questionStep && questions.length > 0 && (
                <QuestionsForm key={detail.id} questions={questions} busy={acting}
                  onSubmit={answers => act(() => answerTask(detail.id, answers))} />
              )}
              {detail.summary && (
                <div style={{ marginTop: 10, padding: '0.6rem 0.75rem', borderRadius: 'var(--r-sm)', background: 'var(--bg-elevated)', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  {detail.summary}
                </div>
              )}

              <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 4 }}>
                {detail.steps.map(step => {
                  const expandable = !!step.output && ['prompt', 'watch', 'verify'].includes(step.kind)
                  const isOpen = open[step.idx] ?? (step.status === 'waiting_approval' && step.kind === 'handoff')
                  return (
                    <div key={step.idx} style={{ borderLeft: '2px solid var(--border-soft)', paddingLeft: 12, marginLeft: 6 }}>
                      <button onClick={() => expandable && setOpen(o => ({ ...o, [step.idx]: !isOpen }))} style={{
                        display: 'flex', alignItems: 'center', gap: 8, width: '100%', background: 'none', border: 'none',
                        padding: '6px 0', cursor: expandable ? 'pointer' : 'default', color: 'var(--text-primary)', textAlign: 'left',
                        fontFamily: 'var(--font-sans)',
                      }}>
                        <StepIcon status={step.status} />
                        <span style={{ fontSize: '0.82rem', fontWeight: 500 }}>{step.title}</span>
                        {step.policy === 'approval' && <span style={{ fontSize: '0.62rem', color: 'var(--warning)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 4, padding: '0 4px' }}>approval</span>}
                        {expandable && (isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />)}
                      </button>
                      {step.detail && step.detail !== 'skip' && (
                        <div style={{ fontSize: '0.74rem', color: step.status === 'failed' ? 'var(--error)' : 'var(--text-tertiary)', marginLeft: 22, marginTop: -2 }}>
                          {step.detail}
                        </div>
                      )}
                      <AnimatePresence>
                        {isOpen && expandable && (
                          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} style={{ marginLeft: 22, overflow: 'hidden' }}>
                            <StepOutput step={step} />
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )
                })}
              </div>

              {detail.needs.length > 0 && (
                <div style={{ marginTop: 14, padding: '0.75rem', borderRadius: 'var(--r-md)', border: '1px solid rgba(245,158,11,0.3)', background: 'var(--warning-muted)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, fontSize: '0.8rem', color: 'var(--warning)', marginBottom: 6 }}>
                    <KeyRound size={13} /> Still needed from you
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {detail.needs.map(n => (
                      <span key={n.id} style={{ fontSize: '0.72rem', fontFamily: 'var(--font-mono)', padding: '2px 6px', borderRadius: 4, background: 'var(--bg-elevated)', color: n.status === 'open' ? 'var(--text-primary)' : 'var(--text-tertiary)', textDecoration: n.status === 'open' ? 'none' : 'line-through' }}>
                        {n.var}
                      </span>
                    ))}
                  </div>
                  {onOpenInbox && <button onClick={onOpenInbox} style={{ ...ghostBtn, marginTop: 8 }}>Open Inbox</button>}
                </div>
              )}
            </GlassCard>
          )}
        </div>
      </div>
    </div>
  )
}

const preStyle: React.CSSProperties = {
  marginTop: 6, maxHeight: 280, overflow: 'auto', whiteSpace: 'pre-wrap', fontSize: '0.72rem',
  fontFamily: 'var(--font-mono)', background: 'var(--bg-elevated)', border: '1px solid var(--border-soft)',
  borderRadius: 'var(--r-sm)', padding: '0.6rem', color: 'var(--text-secondary)',
}
const chip: React.CSSProperties = {
  padding: '0.3rem 0.7rem', borderRadius: 'var(--r-full)', border: '1px solid', fontSize: '0.75rem',
  cursor: 'pointer', fontFamily: 'var(--font-sans)',
}
const field: React.CSSProperties = {
  width: '100%', padding: '0.5rem 0.65rem', borderRadius: 'var(--r-sm)', border: '1px solid var(--border-soft)',
  background: 'var(--bg-elevated)', color: 'var(--text-primary)', fontFamily: 'var(--font-sans)', fontSize: '0.8rem',
  outline: 'none', boxSizing: 'border-box',
}
const ghostBtn: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 5, padding: '0.4rem 0.8rem', borderRadius: 'var(--r-sm)',
  border: '1px solid var(--border-soft)', background: 'var(--bg-elevated)', color: 'var(--text-secondary)',
  fontSize: '0.76rem', cursor: 'pointer', fontFamily: 'var(--font-sans)',
}
function primaryBtn(disabled: boolean): React.CSSProperties {
  return {
    display: 'flex', alignItems: 'center', gap: 5, padding: '0.45rem 0.9rem', borderRadius: 'var(--r-sm)',
    border: 'none', background: disabled ? 'var(--bg-hover)' : 'linear-gradient(135deg, var(--accent) 0%, #8b6fff 100%)',
    color: disabled ? 'var(--text-disabled)' : '#fff', fontSize: '0.78rem', fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer', fontFamily: 'var(--font-sans)',
  }
}
