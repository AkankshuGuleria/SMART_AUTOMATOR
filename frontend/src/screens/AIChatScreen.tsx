/**
 * screens/AIChatScreen.tsx
 * Premium AI chat experience: glass conversation panel, memory refs, action cards, code blocks.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Sparkles, ChevronRight, Copy, Check, Zap, Loader2 } from 'lucide-react'
import {
  sendChatMessage,
  approveAction,
  type ActionCard,
} from '../lib/api'
import AIStatusBadge from '../components/ui/AIStatusBadge'

interface Message {
  id: string
  role: 'user' | 'agent'
  content: string
  timestamp: Date
  intent?: string
  actions?: ActionCard[]
  grounded?: boolean
}

const QUICK_ACTIONS = [
  { label: 'Morning brief', text: 'morning brief' },
  { label: 'What\'s next?', text: 'what should I work on next?' },
  { label: 'Explain repo', text: 'explain repository structure' },
  { label: 'Generate commit', text: 'generate commit message' },
  { label: 'Run tests', text: 'run tests' },
]

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function parseContent(text: string, id: string): React.ReactNode[] {
  const lines = text.split('\n')
  const nodes: React.ReactNode[] = []
  lines.forEach((line, i) => {
    const key = `${id}-${i}`
    // Replies can echo captured file/terminal content, so escape before formatting.
    const processed = escapeHtml(line)
      .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
    if (line.startsWith('• ') || line.startsWith('- ')) {
      nodes.push(
        <div key={key} style={{ display: 'flex', gap: '0.4rem', marginLeft: '0.5rem', lineHeight: 1.6 }}>
          <span style={{ color: 'var(--accent)', flexShrink: 0, marginTop: 2 }}>▸</span>
          <span dangerouslySetInnerHTML={{ __html: processed.slice(2) }} />
        </div>
      )
    } else if (line === '') {
      nodes.push(<div key={key} style={{ height: '0.45rem' }} />)
    } else {
      nodes.push(<div key={key} dangerouslySetInnerHTML={{ __html: processed }} style={{ lineHeight: 1.65 }} />)
    }
  })
  return nodes
}

function describeError(e: unknown): string {
  const raw = e instanceof Error ? e.message : String(e)
  const match = raw.match(/-\s*(\{[\s\S]*\})\s*$/)
  if (match) {
    try {
      const parsed = JSON.parse(match[1]) as { detail?: string }
      if (parsed.detail) return parsed.detail
    } catch {
      return raw
    }
  }
  return raw
}

function TypingDots() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '0.2rem 0' }}>
      {[0, 1, 2].map(i => (
        <motion.span
          key={i}
          animate={{ y: [0, -5, 0] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.18, ease: 'easeInOut' }}
          style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--accent-2)', display: 'inline-block' }}
        />
      ))}
    </div>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }
  return (
    <motion.button
      onClick={handleCopy}
      whileTap={{ scale: 0.9 }}
      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', padding: '0.2rem', borderRadius: 4 }}
    >
      <AnimatePresence mode="wait">
        {copied
          ? <motion.span key="check" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}><Check size={13} color="var(--success)" /></motion.span>
          : <motion.span key="copy" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}><Copy size={13} /></motion.span>
        }
      </AnimatePresence>
    </motion.button>
  )
}

interface Props {
  projectId?: string
  onActivity?: () => void
  /** A message queued from the command palette; sent once on arrival. */
  initialMessage?: string | null
  onInitialMessageSent?: () => void
}

export default function AIChatScreen({ projectId, onActivity, initialMessage, onInitialMessageSent }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [approving, setApproving] = useState<Record<string, boolean>>({})
  const [approveError, setApproveError] = useState<Record<string, string | undefined>>({})
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    setMessages([])
  }, [projectId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, sending])

  const send = useCallback(async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || sending) return
    setInput('')
    setSending(true)
    onActivity?.()
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: trimmed, timestamp: new Date() }
    setMessages(prev => [...prev, userMsg])
    try {
      const res = await sendChatMessage(trimmed, projectId, projectId)
      const agentMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: res.reply ?? res.error ?? 'No response',
        timestamp: new Date(),
        intent: res.intent,
        actions: res.actions ?? [],
        grounded: false,
      }
      setMessages(prev => [...prev, agentMsg])
    } catch (e) {
      const offline = e instanceof TypeError
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: offline
          ? 'Could not reach the backend. Start it with `cd backend && uv run python main.py`.'
          : `Request failed: ${describeError(e)}`,
        timestamp: new Date(),
      }])
    } finally {
      setSending(false)
    }
  }, [sending, projectId, onActivity])

  const sentInitialRef = useRef<string | null>(null)
  useEffect(() => {
    // Ref guard: StrictMode runs effects twice in development.
    if (!initialMessage) {
      sentInitialRef.current = null
    } else if (sentInitialRef.current !== initialMessage) {
      sentInitialRef.current = initialMessage
      onInitialMessageSent?.()
      send(initialMessage)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialMessage])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  const runAction = useCallback(async (messageId: string, actionIndex: number, action: ActionCard) => {
    const actionKey = `${messageId}-${actionIndex}`
    setApproving(prev => ({ ...prev, [actionKey]: true }))
    setApproveError(prev => ({ ...prev, [actionKey]: undefined }))
    try {
      const result = await approveAction(
        action.type ?? '',
        action.params ?? {},
        projectId,
      )
      if (result.executed) {
        setMessages(previous => previous.map(candidate => (
          candidate.id === messageId
            ? {
                ...candidate,
                actions: candidate.actions?.map((pending, index) => (
                  index === actionIndex
                    ? { ...pending, executed: true, result: result.result as Record<string, unknown> }
                    : pending
                )),
              }
            : candidate
        )))
        onActivity?.()
      } else {
        setApproveError(prev => ({ ...prev, [actionKey]: 'Action did not complete.' }))
      }
    } catch (e) {
      setApproveError(prev => ({ ...prev, [actionKey]: describeError(e) }))
    } finally {
      setApproving(prev => ({ ...prev, [actionKey]: false }))
    }
  }, [projectId, onActivity])

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', height: '100%' }}>
      {/* Header */}
      <div style={{
        padding: '0.85rem 1.25rem',
        borderBottom: '1px solid var(--border-soft)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
        background: 'var(--bg-glass)',
        backdropFilter: 'var(--blur-sm)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: 'linear-gradient(135deg, var(--accent) 0%, var(--ai-cyan) 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: 'var(--shadow-glow)',
          }}>
            <Sparkles size={15} color="#fff" strokeWidth={2.5} />
          </div>
          <div>
            <div style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--text-primary)' }}>AI Agent</div>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
              Memory-grounded · Project context
            </div>
          </div>
        </div>
        <AIStatusBadge state={sending ? 'thinking' : 'idle'} label={sending ? 'Thinking…' : 'Ready'} size="sm" />
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {messages.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 200, damping: 24 }}
            style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '1rem', paddingBottom: '2rem' }}
          >
            <motion.div
              animate={{ y: [0, -6, 0] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              style={{
                width: 60, height: 60, borderRadius: 18,
                background: 'linear-gradient(135deg, var(--accent) 0%, var(--ai-cyan) 100%)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: 'var(--shadow-glow)',
              }}
            >
              <Sparkles size={28} color="#fff" />
            </motion.div>
            <div style={{ textAlign: 'center' }}>
              <h2 style={{ marginBottom: '0.4rem', color: 'var(--text-primary)' }}>How can I help?</h2>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)', maxWidth: 360 }}>
                I have access to your full project memory — commits, files, decisions, and context.
              </p>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', justifyContent: 'center', maxWidth: 480 }}>
              {QUICK_ACTIONS.map(a => (
                <motion.button
                  key={a.text}
                  onClick={() => send(a.text)}
                  whileHover={{ y: -2, boxShadow: 'var(--shadow-md)' }}
                  whileTap={{ scale: 0.96 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                  style={{
                    padding: '0.45rem 0.9rem',
                    borderRadius: 'var(--r-full)',
                    border: '1px solid var(--border-soft)',
                    background: 'var(--bg-elevated)',
                    color: 'var(--text-secondary)',
                    fontSize: '0.8rem',
                    cursor: 'pointer',
                    fontFamily: 'var(--font-sans)',
                    display: 'flex', alignItems: 'center', gap: '0.35rem',
                  }}
                >
                  <ChevronRight size={12} color="var(--accent)" />
                  {a.label}
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}

        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 16, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ type: 'spring', stiffness: 300, damping: 28 }}
              style={{
                display: 'flex',
                flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                gap: '0.6rem',
                alignItems: 'flex-end',
              }}
            >
              {/* Avatar */}
              <div style={{
                width: 28, height: 28, borderRadius: 8, flexShrink: 0,
                background: msg.role === 'user'
                  ? 'linear-gradient(135deg, var(--accent-2) 0%, var(--accent) 100%)'
                  : 'linear-gradient(135deg, var(--accent) 0%, var(--ai-cyan) 100%)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '0.7rem', fontWeight: 700, color: '#fff',
                boxShadow: msg.role === 'agent' ? 'var(--shadow-glow)' : undefined,
              }}>
                {msg.role === 'user' ? 'U' : '⚡'}
              </div>

              {/* Bubble */}
              <div style={{ maxWidth: '75%', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                <div style={{
                  padding: '0.75rem 1rem',
                  borderRadius: msg.role === 'user' ? 'var(--r-lg) var(--r-sm) var(--r-lg) var(--r-lg)' : 'var(--r-sm) var(--r-lg) var(--r-lg) var(--r-lg)',
                  background: msg.role === 'user' ? 'linear-gradient(135deg, var(--accent) 0%, #8b6fff 100%)' : 'var(--bg-elevated)',
                  border: msg.role === 'agent' ? '1px solid var(--border-soft)' : 'none',
                  color: msg.role === 'user' ? '#fff' : 'var(--text-primary)',
                  fontSize: '0.85rem',
                  lineHeight: 1.65,
                  boxShadow: msg.role === 'user' ? '0 4px 16px rgba(108,79,255,0.3)' : 'var(--shadow-sm)',
                }}>
                  {parseContent(msg.content, msg.id)}
                </div>

                {/* Metadata row */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start', paddingLeft: msg.role === 'agent' ? '0.25rem' : 0 }}>
                  <span style={{ fontSize: '0.62rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                    {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  {msg.grounded && (
                    <span style={{ fontSize: '0.6rem', background: 'var(--success-muted)', color: 'var(--success)', padding: '0.05rem 0.4rem', borderRadius: 3 }}>
                      memory-grounded
                    </span>
                  )}
                  {msg.intent && (
                    <span style={{ fontSize: '0.6rem', background: 'var(--accent-muted)', color: 'var(--accent-2)', padding: '0.05rem 0.4rem', borderRadius: 3 }}>
                      {msg.intent}
                    </span>
                  )}
                  {msg.role === 'agent' && (
                    <CopyButton text={msg.content} />
                  )}
                </div>

                {msg.actions && msg.actions.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginTop: '0.25rem' }}>
                    {msg.actions.map((action, i) => {
                      const actionKey = `${msg.id}-${i}`
                      const policy = action.policy ?? 'suggest'
                      const needsApproval = !action.executed && (
                        policy === 'suggest'
                        || policy === 'confirm_once'
                        || policy === 'require_approval'
                      )
                      const isApproving = approving[actionKey] ?? false
                      const failure = approveError[actionKey]
                      return (
                        <motion.div
                          key={i}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: 0.1 + i * 0.06, type: 'spring', stiffness: 300, damping: 26 }}
                          style={{
                            padding: '0.6rem 0.85rem',
                            borderRadius: 'var(--r-md)',
                            border: `1px solid ${action.executed ? 'rgba(16,185,129,0.35)' : 'rgba(245,158,11,0.3)'}`,
                            background: action.executed ? 'var(--success-muted)' : 'var(--warning-muted)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: '0.5rem',
                          }}
                        >
                          <div style={{ minWidth: 0 }}>
                            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: action.executed ? 'var(--success)' : 'var(--warning)' }}>
                              {action.type ?? 'Action'}
                            </div>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginTop: 1 }}>
                              {action.policy ?? (action.executed ? 'Executed' : 'Pending approval')}
                            </div>
                            {failure && (
                              <div style={{ fontSize: '0.68rem', color: 'var(--warning)', marginTop: 2 }}>
                                {failure}
                              </div>
                            )}
                          </div>
                          {needsApproval && (
                            <motion.button
                              id={`action-execute-${msg.id}-${i}`}
                              onClick={() => runAction(msg.id, i, action)}
                              disabled={isApproving}
                              whileHover={isApproving ? undefined : { scale: 1.05 }}
                              whileTap={isApproving ? undefined : { scale: 0.95 }}
                              style={{
                                padding: '0.3rem 0.7rem',
                                borderRadius: 'var(--r-sm)',
                                border: '1px solid var(--accent)',
                                background: 'var(--accent)',
                                color: 'white',
                                fontSize: '0.72rem',
                                fontWeight: 600,
                                cursor: isApproving ? 'wait' : 'pointer',
                                opacity: isApproving ? 0.7 : 1,
                                display: 'flex', alignItems: 'center', gap: 4,
                                flexShrink: 0,
                                transition: 'background var(--dur-fast) var(--ease-in-out)',
                              }}
                            >
                              {isApproving
                                ? <motion.span animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 0.9, ease: 'linear' }} style={{ display: 'inline-flex' }}><Loader2 size={11} /></motion.span>
                                : <Zap size={11} />}
                              {isApproving ? 'Executing…' : 'Execute'}
                            </motion.button>
                          )}
                        </motion.div>
                      )
                    })}
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Typing indicator */}
        <AnimatePresence>
          {sending && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 6 }}
              transition={{ type: 'spring', stiffness: 300, damping: 26 }}
              style={{ display: 'flex', gap: '0.6rem', alignItems: 'flex-end' }}
            >
              <div style={{ width: 28, height: 28, borderRadius: 8, background: 'linear-gradient(135deg, var(--accent) 0%, var(--ai-cyan) 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem', color: '#fff', boxShadow: 'var(--shadow-glow)' }}>⚡</div>
              <div style={{ padding: '0.7rem 1rem', background: 'var(--bg-elevated)', borderRadius: 'var(--r-sm) var(--r-lg) var(--r-lg) var(--r-lg)', border: '1px solid var(--border-soft)' }}>
                <TypingDots />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div style={{
        padding: '0.85rem 1rem 1rem',
        borderTop: '1px solid var(--border-soft)',
        flexShrink: 0,
        background: 'var(--bg-glass)',
        backdropFilter: 'var(--blur-sm)',
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: '0.6rem',
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border-soft)',
          borderRadius: 'var(--r-lg)',
          padding: '0.6rem 0.75rem',
          transition: 'border-color var(--dur-fast) var(--ease-in-out), box-shadow var(--dur-fast) var(--ease-in-out)',
          outline: 'none',
        }}
          onFocus={() => {}}
        >
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about your project… (⏎ to send, ⇧⏎ newline)"
            rows={1}
            style={{
              flex: 1,
              background: 'none',
              border: 'none',
              outline: 'none',
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-sans)',
              fontSize: '0.875rem',
              resize: 'none',
              maxHeight: 140,
              lineHeight: 1.6,
              overflowY: 'auto',
            }}
            onInput={e => {
              const el = e.currentTarget
              el.style.height = 'auto'
              el.style.height = Math.min(el.scrollHeight, 140) + 'px'
            }}
          />
          <motion.button
            onClick={() => send(input)}
            disabled={!input.trim() || sending}
            whileHover={input.trim() && !sending ? { scale: 1.08 } : undefined}
            whileTap={input.trim() && !sending ? { scale: 0.93 } : undefined}
            transition={{ type: 'spring', stiffness: 400, damping: 20 }}
            style={{
              width: 34, height: 34,
              borderRadius: 'var(--r-sm)',
              border: 'none',
              cursor: input.trim() && !sending ? 'pointer' : 'not-allowed',
              background: input.trim() && !sending
                ? 'linear-gradient(135deg, var(--accent) 0%, #8b6fff 100%)'
                : 'var(--bg-hover)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
              transition: 'background var(--dur-fast) var(--ease-in-out)',
              boxShadow: input.trim() && !sending ? 'var(--shadow-glow)' : 'none',
            }}
          >
            <Send size={15} color={input.trim() && !sending ? '#fff' : 'var(--text-disabled)'} />
          </motion.button>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
          {QUICK_ACTIONS.slice(0, 3).map(a => (
            <button
              key={a.text}
              onClick={() => send(a.text)}
              style={{
                padding: '0.25rem 0.6rem',
                borderRadius: 'var(--r-full)',
                border: '1px solid var(--border-soft)',
                background: 'transparent',
                color: 'var(--text-tertiary)',
                fontSize: '0.7rem',
                cursor: 'pointer',
                fontFamily: 'var(--font-sans)',
                transition: 'all var(--dur-fast) var(--ease-in-out)',
              }}
              onMouseEnter={e => { (e.target as HTMLButtonElement).style.borderColor = 'var(--accent)'; (e.target as HTMLButtonElement).style.color = 'var(--accent-2)' }}
              onMouseLeave={e => { (e.target as HTMLButtonElement).style.borderColor = 'var(--border-soft)'; (e.target as HTMLButtonElement).style.color = 'var(--text-tertiary)' }}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
