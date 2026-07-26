/**
 * screens/QueryChat.tsx — AUTOMATA Memory Query / Agent Chat screen
 *
 * Redesigned against:
 * - ui-ux-pro-max: accessibility, loading feedback, touch targets, keyboard nav
 * - taste-skill: premium feel, restrained chrome, no generic slop
 * - superpowers verification-before-completion: explicit loading/error/grounded evidence
 */

import React, { useState, useRef, useEffect } from "react";
import { queryMemory, type QueryResult, generateCommitMessage, findAuthenticationCode, continuePreviousWork, generateProjectSummary, startDevEnvironment, type CommitMessageResult, type FindAuthResult, type ContinueWorkResult, type ProjectSummaryResult, type StartDevEnvResult } from "../lib/api";

type ActionLabel = string;

interface ChatMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  grounded?: boolean;
  timestamp: Date;
}

interface QueryChatProps {
  projectId?: string;
  repoPath?: string;
}

export const QueryChatScreen: React.FC<QueryChatProps> = ({ projectId, repoPath }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<ActionLabel | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const addMessage = (role: "user" | "agent", content: string, grounded = false) => {
    const msg: ChatMessage = {
      id: crypto.randomUUID(),
      role,
      content,
      grounded,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, msg]);
  };

  const runAction = async (label: ActionLabel, action: () => Promise<CommitMessageResult | FindAuthResult | ContinueWorkResult | ProjectSummaryResult | StartDevEnvResult>) => {
    if (!projectId || actionLoading) return;
    setActionLoading(label);
    addMessage("user", `Action: ${label}`);
    try {
      const result = await action();
      let content = "";
      if ("commit_message" in result) content = String((result as { commit_message?: string | null }).commit_message ?? "")
      else if ("results" in result) content = `Found ${(result as { results?: Array<unknown> }).results?.length ?? 0} auth-related memories.`
      else if ("suggestion" in result) content = String((result as { suggestion?: string | null }).suggestion ?? "")
      else if ("summary" in result) content = String((result as { summary?: string | null }).summary ?? "")
      else if ("status" in result) content = `Dev environment: ${(result as { status?: string }).status ?? ""}`
      if ("error" in result && result.error) content += `\nError: ${result.error}`
      addMessage("agent", content, true);
    } catch (err: unknown) {
      addMessage("agent", `Action failed: ${err instanceof Error ? err.message : "Unknown error"}`, false);
    } finally {
      setActionLoading(null);
    }
  };

  const sendQuery = async () => {
    const question = input.trim();
    if (!question || loading) return;
    addMessage("user", question);
    setInput("");
    setLoading(true);
    try {
      const result: QueryResult = await queryMemory(question, projectId);
      addMessage("agent", result.answer ?? "No answer.", result.grounded);
    } catch (err: unknown) {
      addMessage("agent", `Query failed: ${err instanceof Error ? err.message : "Unknown error"}`, false);
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

      <div className="chat-actions">
        <button id="action-commit" className="automata-btn-primary" disabled={!projectId || !repoPath || actionLoading === "Generate commit message"} onClick={() => runAction("Generate commit message", () => generateCommitMessage(projectId!, repoPath!))}>
          {actionLoading === "Generate commit message" ? "Generating…" : "Generate commit message"}
        </button>
        <button id="action-auth" className="automata-btn-primary" disabled={!projectId || actionLoading === "Find auth code"} onClick={() => runAction("Find auth code", () => findAuthenticationCode(projectId!))}>
          {actionLoading === "Find auth code" ? "Searching…" : "Find auth code"}
        </button>
        <button id="action-continue" className="automata-btn-primary" disabled={!projectId || actionLoading === "Continue previous work"} onClick={() => runAction("Continue previous work", () => continuePreviousWork(projectId!))}>
          {actionLoading === "Continue previous work" ? "Planning…" : "Continue previous work"}
        </button>
        <button id="action-summary" className="automata-btn-primary" disabled={!projectId || actionLoading === "Project summary"} onClick={() => runAction("Project summary", () => generateProjectSummary(projectId!))}>
          {actionLoading === "Project summary" ? "Summarizing…" : "Project summary"}
        </button>
        <button id="action-dev" className="automata-btn-primary" disabled={!projectId || actionLoading === "Start dev environment"} onClick={() => runAction("Start dev environment", () => startDevEnvironment(projectId!))}>
          {actionLoading === "Start dev environment" ? "Starting…" : "Start dev environment"}
        </button>
      </div>

      <div className="chat-messages" role="log" aria-live="polite" aria-label="Conversation">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>Ask anything about your project.</p>
            <p className="chat-examples">
              Try: “What did I finish yesterday?” · “Where is the auth code?” · “Generate a commit message for my staged changes.”
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
          disabled={loading || !!actionLoading}
          aria-label="Ask a question about your project"
          autoComplete="off"
        />
        <button
          id="query-chat-send-btn"
          className="automata-btn-primary"
          onClick={sendQuery}
          disabled={!input.trim() || loading || !!actionLoading}
          aria-label="Send query"
        >
          Send
        </button>
      </div>
    </section>
  );
};

export default QueryChatScreen;
