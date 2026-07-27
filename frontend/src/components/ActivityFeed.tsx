/**
 * components/ActivityFeed.tsx — AUTOMATA chronological activity/audit feed.
 *
 * Owns: Rendering decisions, commits, and terminal commands from the agent
 *       activity log. Shows meaningful empty state and loading skeletons.
 * Never: Talks directly to CockroachDB or Bedrock.
 */

import { useState, useEffect } from "react";
import { getActivityFeed, type ActivityItem } from "../lib/api";

interface ActivityFeedProps {
  projectId: string;
  onClearBadge: () => void;
}

const KIND_ICONS: Record<string, string> = {
  commit:   "⬡",
  decision: "⚡",
  terminal: "›_",
  file:     "◈",
};

function SkeletonItem() {
  return (
    <div style={{
      border: "1px solid var(--color-border-soft)",
      borderRadius: "var(--radius-lg)",
      padding: "0.9rem 1rem",
      background: "var(--color-bg-surface)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.5rem" }}>
        <div style={{ width: 48, height: 16, borderRadius: 4, background: "var(--color-bg-hover)", animation: "pulse 1.4s ease-in-out infinite" }} />
        <div style={{ flex: 1, height: 12, borderRadius: 4, background: "var(--color-bg-hover)", animation: "pulse 1.4s ease-in-out infinite" }} />
      </div>
      <div style={{ height: 14, borderRadius: 4, background: "var(--color-bg-elevated)", animation: "pulse 1.4s ease-in-out infinite", width: "70%" }} />
    </div>
  );
}

function ActivityCard({ item }: { item: ActivityItem }) {
  const [expanded, setExpanded] = useState(false);
  const icon = KIND_ICONS[item.kind] || "·";
  const timeStr = item.created_at
    ? new Date(item.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
    : "";

  return (
    <div
      className="card animate-slide-up"
      style={{ padding: "0.85rem 1rem", cursor: item.detail ? "pointer" : "default" }}
      onClick={() => item.detail && setExpanded((v) => !v)}
      role={item.detail ? "button" : undefined}
      tabIndex={item.detail ? 0 : undefined}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem" }}>
        <span style={{
          fontSize: "0.7rem",
          fontFamily: "var(--font-mono)",
          color: "var(--color-text-tertiary)",
          marginTop: "2px",
          minWidth: 18,
        }}>
          {icon}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.3rem" }}>
            <span className={`kind-badge ${item.kind}`}>{item.kind}</span>
            {timeStr && (
              <span style={{ fontSize: "0.68rem", color: "var(--color-text-tertiary)" }}>{timeStr}</span>
            )}
            {item.detail && (
              <span style={{ marginLeft: "auto", fontSize: "0.65rem", color: "var(--color-text-tertiary)" }}>
                {expanded ? "▲" : "▼"}
              </span>
            )}
          </div>
          <p style={{ fontSize: "0.82rem", color: "var(--color-text-primary)", lineHeight: 1.5, wordBreak: "break-word" }}>
            {item.summary}
          </p>
          {expanded && item.detail && (
            <p style={{ marginTop: "0.5rem", fontSize: "0.75rem", color: "var(--color-text-secondary)", fontFamily: "var(--font-mono)", wordBreak: "break-all" }}>
              {item.detail}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ActivityFeed({ projectId, onClearBadge }: ActivityFeedProps) {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getActivityFeed(projectId)
      .then(({ items }) => {
        if (!cancelled) setItems(items || []);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load activity");
        if (!cancelled) setItems([]);
      })
      .finally(() => {
        if (!cancelled) { setLoading(false); onClearBadge(); }
      });
    return () => { cancelled = true; };
  }, [projectId]);

  if (loading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
        {[1, 2, 3].map((i) => <SkeletonItem key={i} />)}
      </div>
    );
  }

  if (error) {
    return (
      <div className="automata-empty">
        <span style={{ fontSize: "1.5rem" }}>⚠</span>
        <p style={{ color: "var(--color-error)" }}>Failed to load activity</p>
        <p style={{ fontSize: "0.75rem", color: "var(--color-text-tertiary)" }}>{error}</p>
        <p style={{ fontSize: "0.75rem", color: "var(--color-text-tertiary)" }}>Make sure the backend is running on port 8000</p>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="automata-empty">
        <span style={{ fontSize: "2rem", opacity: 0.4 }}>◈</span>
        <p>No activity yet</p>
        <p style={{ fontSize: "0.78rem" }}>Activity appears here as you work with AUTOMATA.</p>
        <p style={{ fontSize: "0.75rem", color: "var(--color-text-tertiary)", marginTop: "0.25rem" }}>
          Try chatting with the agent or opening a project.
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
      <div style={{ fontSize: "0.75rem", color: "var(--color-text-tertiary)", marginBottom: "0.25rem" }}>
        {items.length} event{items.length !== 1 ? "s" : ""}
      </div>
      {items.map((item, i) => (
        <ActivityCard key={item.id || i} item={item} />
      ))}
    </div>
  );
}
