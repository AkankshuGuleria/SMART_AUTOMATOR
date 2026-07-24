/**
 * screens/QueryChat.tsx — AUTOMATA Memory Query / Agent Chat screen
 *
 * Phase 0: Stub screen with input/response layout shell.
 * Phase 2: Wire to api.queryMemory() + real grounded answers from CockroachDB + Bedrock.
 * Ref:     PROJECT.md §13 (demo queries), SKILLS.md §5 (retrieval quality),
 *          SKILLS.md §6 (output naturalness — no chatbot filler in responses).
 */

import React, { useState, useRef, useEffect } from "react";
import { queryMemory, type QueryResult } from "../lib/api";

interface ChatMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  grounded?: boolean;
  timestamp: Date;
}

interface QueryChatProps {
  projectId?: string;
}

export const QueryChatScreen: React.FC<QueryChatProps> = ({ projectId }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendQuery = async () => {
    const question = input.trim();
    if (!question || loading) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const result: QueryResult = await queryMemory(question, projectId);

      const agentMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "agent",
        content: result.answer ?? "No answer available yet — implement in Phase 2.",
        grounded: result.grounded,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, agentMsg]);
    } catch (err: unknown) {
      const errMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "agent",
        content: `Query failed: ${err instanceof Error ? err.message : "Unknown error"}`,
        grounded: false,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendQuery();
    }
  };

  return (
    <section className="automata-query-chat" aria-labelledby="chat-heading">
      <h1 id="chat-heading" className="visually-hidden">Memory Query</h1>

      <div className="chat-messages" role="log" aria-live="polite" aria-label="Conversation">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>Ask anything about your project.</p>
            <p className="chat-examples">
              Try: "What did I finish yesterday?" · "Where is the auth code?" ·
              "Generate a commit message for my staged changes."
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`chat-message chat-message--${msg.role}`}
          >
            <div className="chat-bubble">
              <p>{msg.content}</p>
              {msg.role === "agent" && msg.grounded === false && msg.content.includes("Phase 2") && (
                <span className="chat-badge chat-badge--stub">Phase 0 stub</span>
              )}
              {msg.role === "agent" && msg.grounded === true && (
                <span className="chat-badge chat-badge--grounded">Grounded in memory</span>
              )}
            </div>
            <time className="chat-time" dateTime={msg.timestamp.toISOString()}>
              {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </time>
          </div>
        ))}

        {loading && (
          <div className="chat-message chat-message--agent">
            <div className="chat-bubble chat-bubble--loading" aria-label="Agent thinking">
              <span className="automata-spinner" aria-hidden="true" />
              <span>Retrieving memory…</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-row">
        <input
          id="query-chat-input"
          type="text"
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your project…"
          disabled={loading}
          aria-label="Ask a question about your project"
          autoComplete="off"
        />
        <button
          id="query-chat-send-btn"
          className="automata-btn-primary"
          onClick={sendQuery}
          disabled={!input.trim() || loading}
          aria-label="Send query"
        >
          Send
        </button>
      </div>
    </section>
  );
};

export default QueryChatScreen;
