/**
 * screens/AIChatScreen.tsx
 * Premium AI chat experience: glass conversation panel, memory refs, action cards, code blocks.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Sparkles, ChevronRight, Copy, Check, Zap } from 'lucide-react'
import {
  sendChatMessage,
  getToolStatus,
  approveAction,
  type ActionCard,
} from '../lib/api'
import AIStatusBadge from '../components/ui/AIStatusBadge'

const DEMO_PROJECT_ID = '2efec7e0-92db-4591-9594-026ff8399a3c'

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

function parseContent(text: string, id: string): React.ReactNode[] {
  const lines = text.split('\n')
  const nodes: React.ReactNode[] = []
  lines.forEach((line, i) => {
    const key = `${id}-${i}`
    const processed = line
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
  onOpenProject?: (id: string) => void
}

export default function AIChatScreen({ projectId = DEMO_PROJECT_ID, onActivity }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const pollTool = useCallback(async () => {
    try {
      const s = await getToolStatus()
      if (s.tools?.length) console.log('Tools:', s.tools)
    } catch { /* ignore */ }
  }, [])

  const send = useCallback(async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || sending) return
    setInput('')
    setSending(true)
    onActivity?.()
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: trimmed, timestamp: new Date() }
    setMessages(prev => [...prev, userMsg])
    try {
      const res = await sendChatMessage(trimmed, projectId)
      const agentMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: res.reply ?? res.error ?? 'No response',
        timestamp: new Date(),
        intent: res.intent,
        actions: [...(res.actions ?? []), ...(res.executed_actions ?? [])],
        grounded: false,
      }
      setMessages(prev => [...prev, agentMsg])
      if (res.actions?.length) pollTool()
    } catch (e) {
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: 'Could not reach the backend. Make sure the backend is running (`cd backend && uv run python main.py`).',
        timestamp: new Date(),
      }])
    } finally {
      setSending(false)
    }
  }, [sending, projectId, onActivity, pollTool])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

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
                    {msg.actions.map((action, i) => (
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
                        <div>
                          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: action.executed ? 'var(--success)' : 'var(--warning)' }}>
                            {action.type ?? 'Action'}
                          </div>
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginTop: 1 }}>
                            {action.policy ?? (action.executed ? 'Executed' : 'Pending approval')}
                          </div>
                        </div>
                        {!action.executed && (
                          <motion.button
                            onClick={() => approveAction(action.type ?? '', {}, projectId).catch(() => {})}
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            style={{
                              padding: '0.3rem 0.7rem',
                              borderRadius: 'var(--r-sm)',
                              border: '1px solid rgba(245,158,11,0.4)',
                              background: 'var(--warning-muted)',
                              color: 'var(--warning)',
                              fontSize: '0.72rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'flex', alignItems: 'center', gap: 4,
                            }}
                          >
                            <Zap size={11} /> Run
                          </motion.button>
                        )}
                      </motion.div>
                    ))}
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
