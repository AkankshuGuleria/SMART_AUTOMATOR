/**
 * components/ChatPanel.tsx — AUTOMATA primary chat interface.
 *
 * Owns: chat input, message thread, action cards, inline provenance.
 * Never: talks to CockroachDB or Bedrock directly.
 */

import { useState, useEffect, useRef } from "react";
import { sendChatMessage, getToolStatus, type ToolStatus, type ActionCard } from "../lib/api";

interface ChatPanelProps {
  projectId: string;
  onActivity: () => void;
  onOpenProject: (id: string) => void;
  cmdPaletteOpen: boolean;
  onCloseCmdPalette: () => void;
}

interface Message {
  id: string;
  role: "user" | "agent";
  content: string;
  timestamp: Date;
  intent?: string;
  actions?: ActionCard[];
  grounded?: boolean;
  toolStatus?: ToolStatus[];
}

export default function ChatPanel({ projectId, onActivity }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [tools, setTools] = useState<ToolStatus[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    getToolStatus().then(({ tools }) => setTools(tools || []))
  }, []);

  const send = async () => {
    const question = input.trim();
    if (!question || loading) return;
    const userMsg: Message = { id: crypto.randomUUID(), role: "user", content: question, timestamp: new Date() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    try {
      const result = await sendChatMessage(question, projectId, projectId, true);
      const agentMsg: Message = {
        id: crypto.randomUUID(),
        role: "agent",
        content: result.reply || "OK",
        timestamp: new Date(),
        intent: result.intent,
        actions: result.actions || [],
        grounded: true,
      };
      if (result.error) {
        agentMsg.content += `\nError: ${result.error}`;
      }
      setMessages((prev) => [...prev, agentMsg]);
      onActivity();
    } catch (err: unknown) {
      setMessages((prev) => [...prev, {
        id: crypto.randomUUID(),
        role: "agent",
        content: `Query failed: ${err instanceof Error ? err.message : "Unknown error"}`,
        timestamp: new Date(),
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100dvh' }}>
      <div style={{ flex: 1, overflow: 'auto', padding: '1rem' }}>
        {messages.length === 0 && (
          <div style={{ opacity: 0.8 }}>
            <p>Ask anything about your project.</p>
            <p style={{ fontSize: '0.8rem', opacity: 0.75 }}>Try resume, run tests, explain repo, or generate commit message.</p>
            <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {['Resume where I left off', 'Explain repository', 'Run tests', 'Generate commit message'].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => { setInput(suggestion); }}
                  style={{
                    padding: '0.35rem 0.7rem',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--color-border-soft)',
                    background: 'transparent',
                    color: 'var(--color-text-secondary)',
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                  }}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} style={{ marginBottom: '0.75rem' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--color-text-tertiary)' }}>{msg.role === 'user' ? 'You' : 'AUTOMATA'} · {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
            <div style={{ background: msg.role === 'user' ? 'var(--color-accent-muted)' : 'transparent', padding: '0.6rem 0.8rem', borderRadius: 'var(--radius-md)', border: msg.role === 'user' ? 'none' : '1px solid var(--color-border-soft)', color: 'var(--color-text-primary)' }}>
              {msg.content}
              {msg.grounded && <span style={{ marginLeft: '0.5rem', fontSize: '0.65rem', color: 'var(--color-success)' }}>Grounded in memory</span>}
            </div>
            {msg.actions && msg.actions.length > 0 && (
              <div style={{ marginTop: '0.4rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                    {msg.actions!.map((a: ActionCard, i) => (
                  <div key={i} style={{ fontSize: '0.75rem', background: 'var(--color-bg-surface)', border: '1px solid var(--color-border-soft)', borderRadius: 'var(--radius-md)', padding: '0.5rem' }}>
                    <div><strong>{String(a.type || 'action')}</strong> · {String(a.policy || '')}</div>
                    {a.executed ? <div style={{ color: 'var(--color-success)' }}>Executed · {a.executed_at ? new Date(a.executed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}</div> : <div style={{ color: 'var(--color-warning)' }}>Suggested · {a.provenance || ''}</div>}
                    {a.executed_at && (
                      <details style={{ marginTop: '0.35rem' }}>
                        <summary style={{ cursor: 'pointer', fontSize: '0.7rem', color: 'var(--color-text-tertiary)' }}>Provenance</summary>
                        <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.7rem', marginTop: '0.25rem' }}>{JSON.stringify(a, null, 2)}</pre>
                      </details>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div style={{ marginBottom: '0.75rem' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--color-text-tertiary)' }}>AUTOMATA · thinking</div>
            <div style={{ background: 'transparent', border: '1px solid var(--color-border-soft)', padding: '0.6rem 0.8rem', borderRadius: 'var(--radius-md)', color: 'var(--color-text-primary)' }}>
              <span className="automata-spinner" aria-hidden="true" /> Retrieve/executing…
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div style={{ borderTop: '1px solid var(--color-border-soft)', padding: '0.75rem', background: 'var(--color-bg-surface)' }}>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            id="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
            placeholder="Ask anything…"
            disabled={loading}
            style={{
              flex: 1,
              padding: '0.6rem 0.8rem',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border-soft)',
              background: 'transparent',
              color: 'var(--color-text-primary)',
              fontSize: '0.9rem',
            }}
          />
          <button id="chat-send-btn" onClick={send} disabled={!input.trim() || loading} style={{ padding: '0.6rem 0.9rem', borderRadius: 'var(--radius-md)', border: 'none', background: 'var(--color-accent)', color: '#fff', cursor: 'pointer' }}>
            Send
          </button>
        </div>
        {tools.length > 0 && (
          <div style={{ marginTop: '0.5rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {tools.map((t) => (
                <span key={t.name} style={{ fontSize: '0.65rem', padding: '0.2rem 0.5rem', borderRadius: '999px', border: '1px solid var(--color-border-soft)', color: 'var(--color-text-tertiary)' }}>{t.name}: {t.available ? 'connected' : 'offline'}</span>
              ))}
          </div>
        )}
      </div>
    </div>
  );
}
