/**
 * components/ChatPanel.tsx — AUTOMATA primary chat interface.
 *
 * Owns: chat input, message thread, action cards, inline provenance.
 * Never: talks to CockroachDB or Bedrock directly.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { sendChatMessage, getToolStatus, type ToolStatus, type ActionCard } from "../lib/api";

interface ChatPanelProps {
  projectId: string;
  onActivity?: () => void;
  onOpenProject?: (id: string) => void;
  cmdPaletteOpen?: boolean;
  onCloseCmdPalette?: () => void;
}

interface Message {
  id: string;
  role: "user" | "agent";
  content: string;
  timestamp: Date;
  intent?: string;
  actions?: ActionCard[];
  grounded?: boolean;
}

const QUICK_ACTIONS = [
  { label: "🌐 Open ChatGPT", text: "open browser to chatgpt.com" },
  { label: "📁 Explain repo", text: "explain repository" },
  { label: "▶ Run tests", text: "run tests" },
  { label: "💬 Generate commit", text: "generate commit message" },
  { label: "📋 What's next?", text: "what should I work on next?" },
  { label: "🌅 Morning brief", text: "morning brief" },
];

function TypingIndicator() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "4px", padding: "0.4rem 0" }}>
      <span className="typing-dot" />
      <span className="typing-dot" />
      <span className="typing-dot" />
    </div>
  );
}

function parseMarkdownLike(text: string, msgId: string): React.ReactNode[] {
  const lines = text.split("\n");
  const nodes: React.ReactNode[] = [];

  lines.forEach((line, i) => {
    const key = `${msgId}-line-${i}`;
    // Bold **text**
    const boldReplaced = line.replace(/\*\*(.+?)\*\*/g, (_, t) => `<b>${t}</b>`);
    // Inline code `code`
    const codeReplaced = boldReplaced.replace(/`([^`]+)`/g, (_, t) => `<code>${t}</code>`);

    if (line.startsWith("\u2022 ") || line.startsWith("- ")) {
      nodes.push(
        <div key={key} style={{ display: "flex", gap: "0.4rem", marginLeft: "0.5rem" }}>
          <span style={{ color: "var(--color-accent)", flexShrink: 0 }}>•</span>
          <span dangerouslySetInnerHTML={{ __html: codeReplaced.slice(2) }} />
        </div>
      );
    } else if (line === "") {
      nodes.push(<div key={key} style={{ height: "0.4rem" }} />);
    } else {
      nodes.push(
        <div key={key} dangerouslySetInnerHTML={{ __html: codeReplaced }} />
      );
    }
  });

  return nodes;
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  const timeStr = msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <div className="animate-slide-up" style={{ marginBottom: "1rem" }}>
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "0.4rem",
        marginBottom: "0.3rem",
        justifyContent: isUser ? "flex-end" : "flex-start",
      }}>
        {!isUser && (
          <span style={{
            width: 22, height: 22,
            borderRadius: "50%",
            background: "linear-gradient(135deg, #7c5af4, #4f46e5)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "0.6rem", fontWeight: 700, color: "#fff",
            flexShrink: 0,
          }}>A</span>
        )}
        <span style={{ fontSize: "0.68rem", color: "var(--color-text-tertiary)" }}>
          {isUser ? "You" : "AUTOMATA"} · {timeStr}
        </span>
        {msg.grounded && (
          <span style={{
            fontSize: "0.6rem", padding: "0.1rem 0.4rem",
            borderRadius: "var(--radius-full)",
            background: "var(--color-success-muted)",
            color: "var(--color-success)",
            border: "1px solid rgba(52,211,153,0.25)",
            fontWeight: 500,
          }}>
            ✓ Grounded
          </span>
        )}
      </div>

      <div style={{
        maxWidth: "88%",
        marginLeft: isUser ? "auto" : "0",
        background: isUser
          ? "linear-gradient(135deg, rgba(124,90,244,0.3), rgba(79,70,229,0.2))"
          : "var(--color-bg-surface)",
        border: isUser
          ? "1px solid rgba(124,90,244,0.3)"
          : "1px solid var(--color-border-soft)",
        borderRadius: isUser ? "var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-lg)" : "var(--radius-sm) var(--radius-lg) var(--radius-lg) var(--radius-lg)",
        padding: "0.7rem 0.95rem",
        color: "var(--color-text-primary)",
        fontSize: "0.875rem",
        lineHeight: 1.65,
      }}>
        {isUser ? msg.content : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.15rem" }}>
            {parseMarkdownLike(msg.content, msg.id)}
          </div>
        )}
      </div>

      {/* Action cards */}
      {!isUser && msg.actions && msg.actions.length > 0 && (
        <div style={{ maxWidth: "88%", marginTop: "0.5rem", display: "flex", flexDirection: "column", gap: "0.4rem" }}>
          {msg.actions.map((a: ActionCard, i) => (
            <ActionCardView key={i} action={a} />
          ))}
        </div>
      )}
    </div>
  );
}

function ActionCardView({ action }: { action: ActionCard }) {
  const [open, setOpen] = useState(false);
  const isExecuted = action.executed;
  const label = String(action.type || "action").replace(/_/g, " ");

  return (
    <div
      className={`action-card ${isExecuted ? "executed" : "suggested"}`}
      style={{ cursor: "pointer" }}
      onClick={() => setOpen((v) => !v)}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <span style={{
          fontSize: "0.65rem",
          padding: "0.15rem 0.5rem",
          borderRadius: "var(--radius-full)",
          background: isExecuted ? "var(--color-success-muted)" : "var(--color-warning-muted)",
          color: isExecuted ? "var(--color-success)" : "var(--color-warning)",
          border: `1px solid ${isExecuted ? "rgba(52,211,153,0.3)" : "rgba(251,191,36,0.3)"}`,
          fontWeight: 600,
          textTransform: "uppercase" as const,
          letterSpacing: "0.05em",
        }}>
          {isExecuted ? "✓ Done" : "⟳ Suggested"}
        </span>
        <span style={{ fontSize: "0.78rem", color: "var(--color-text-secondary)", textTransform: "capitalize" as const }}>
          {label}
        </span>
        <span style={{ marginLeft: "auto", fontSize: "0.65rem", color: "var(--color-text-tertiary)" }}>
          {open ? "▲" : "▼"}
        </span>
      </div>
      {action.provenance && (
        <p style={{ fontSize: "0.72rem", color: "var(--color-text-tertiary)", marginTop: "0.3rem" }}>
          {action.provenance}
        </p>
      )}
      {open && (
        <pre style={{ marginTop: "0.5rem", fontSize: "0.7rem" }}>
          {JSON.stringify(action, null, 2)}
        </pre>
      )}
    </div>
  );
}

export default function ChatPanel({
  projectId,
  onActivity = () => {},
  onOpenProject = () => {},
  cmdPaletteOpen = false,
  onCloseCmdPalette = () => {},
}: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [tools, setTools] = useState<ToolStatus[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    // Non-blocking tool status check — ignore errors
    getToolStatus()
      .then(({ tools }) => setTools(tools || []))
      .catch(() => {});
  }, []);

  // Focus input when cmd palette closes
  useEffect(() => {
    if (!cmdPaletteOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [cmdPaletteOpen]);

  const send = useCallback(async (text?: string) => {
    const question = (text ?? input).trim();
    if (!question || loading) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const result = await sendChatMessage(question, projectId, projectId, true);
      const agentMsg: Message = {
        id: crypto.randomUUID(),
        role: "agent",
        content: result.reply || "Done.",
        timestamp: new Date(),
        intent: result.intent,
        actions: result.actions || [],
        grounded: (result.executed_actions?.length ?? 0) > 0,
      };
      if (result.error) {
        agentMsg.content += `\n\n⚠ Error: ${result.error}`;
      }
      setMessages((prev) => [...prev, agentMsg]);
      onActivity();
    } catch (err: unknown) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "agent",
          content: `Connection failed: ${err instanceof Error ? err.message : "Unknown error"}.\n\nMake sure the backend is running:\n\`cd backend && python main.py\``,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, projectId, onActivity]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", position: "relative" }}>
      {/* Message list */}
      <div style={{ flex: 1, overflow: "auto", padding: "1.25rem 1.25rem 0" }}>
        {messages.length === 0 && (
          <div className="animate-fade-in" style={{ marginBottom: "1.5rem" }}>
            {/* Hero */}
            <div style={{
              background: "linear-gradient(135deg, rgba(124,90,244,0.12), rgba(79,70,229,0.06))",
              border: "1px solid rgba(124,90,244,0.2)",
              borderRadius: "var(--radius-xl)",
              padding: "1.5rem",
              marginBottom: "1.25rem",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.75rem" }}>
                <div style={{
                  width: 36, height: 36,
                  background: "linear-gradient(135deg, #7c5af4, #4f46e5)",
                  borderRadius: "50%",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: "1rem", color: "#fff", fontWeight: 700,
                }}>A</div>
                <div>
                  <p style={{ fontWeight: 600, fontSize: "0.9rem" }}>AUTOMATA is ready</p>
                  <p style={{ fontSize: "0.75rem", color: "var(--color-text-tertiary)" }}>Persistent memory · {projectId.slice(0, 8)}…</p>
                </div>
              </div>
              <p style={{ fontSize: "0.82rem", color: "var(--color-text-secondary)", lineHeight: 1.65 }}>
                I remember your projects across sessions. Ask me anything about your codebase,
                open apps, run commands, or restore your workspace.
              </p>
            </div>

            {/* Quick action chips */}
            <p style={{ fontSize: "0.72rem", color: "var(--color-text-tertiary)", marginBottom: "0.5rem", fontWeight: 500, letterSpacing: "0.05em", textTransform: "uppercase" }}>
              Quick actions
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
              {QUICK_ACTIONS.map((qa) => (
                <button
                  key={qa.text}
                  className="chip"
                  onClick={() => send(qa.text)}
                >
                  {qa.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}

        {loading && (
          <div className="animate-fade-in" style={{ marginBottom: "0.75rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.3rem" }}>
              <span style={{
                width: 22, height: 22,
                borderRadius: "50%",
                background: "linear-gradient(135deg, #7c5af4, #4f46e5)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "0.6rem", fontWeight: 700, color: "#fff",
              }}>A</span>
              <span style={{ fontSize: "0.68rem", color: "var(--color-text-tertiary)" }}>AUTOMATA · thinking</span>
            </div>
            <div style={{
              background: "var(--color-bg-surface)",
              border: "1px solid var(--color-border-soft)",
              borderRadius: "var(--radius-sm) var(--radius-lg) var(--radius-lg) var(--radius-lg)",
              padding: "0.7rem 0.95rem",
              display: "inline-block",
            }}>
              <TypingIndicator />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} style={{ height: 1 }} />
      </div>

      {/* Input bar */}
      <div style={{
        borderTop: "1px solid var(--color-border-soft)",
        padding: "0.85rem 1.25rem",
        background: "var(--color-bg-surface)",
        backdropFilter: "blur(12px)",
      }}>
        {/* Tool status pills */}
        {tools.length > 0 && (
          <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", marginBottom: "0.6rem" }}>
            {tools.map((t) => (
              <span key={t.name} className="chip" style={{ fontSize: "0.62rem", cursor: "default" }}>
                <span className={`status-dot ${t.available ? "online" : "offline"}`} style={{ width: 5, height: 5 }} />
                {t.name}
              </span>
            ))}
          </div>
        )}

        <div style={{ display: "flex", gap: "0.6rem", alignItems: "center" }}>
          <input
            ref={inputRef}
            id="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything… (open browser, run tests, explain repo)"
            disabled={loading}
            autoFocus
            style={{
              flex: 1,
              padding: "0.65rem 1rem",
              borderRadius: "var(--radius-lg)",
              border: "1px solid var(--color-border-soft)",
              background: "var(--color-bg-elevated)",
              color: "var(--color-text-primary)",
              fontSize: "0.875rem",
              fontFamily: "var(--font-sans)",
              outline: "none",
              transition: "border-color var(--transition-fast), box-shadow var(--transition-fast)",
            }}
            onFocus={(e) => {
              e.target.style.borderColor = "var(--color-accent)";
              e.target.style.boxShadow = "0 0 0 3px var(--color-accent-muted)";
            }}
            onBlur={(e) => {
              e.target.style.borderColor = "var(--color-border-soft)";
              e.target.style.boxShadow = "none";
            }}
          />
          <button
            id="chat-send-btn"
            className="btn btn-primary"
            onClick={() => send()}
            disabled={!input.trim() || loading}
            style={{ flexShrink: 0 }}
          >
            {loading ? <span className="automata-spinner" style={{ width: 14, height: 14 }} /> : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
