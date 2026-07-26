/**
 * components/ActivityFeed.tsx — AUTOMATA chronological activity/audit feed.
 */

import { useState, useEffect } from "react";
import { getActivityFeed, type ActivityItem } from "../lib/api";

interface ActivityFeedProps {
  projectId: string;
  onClearBadge: () => void;
}

export default function ActivityFeed({ projectId, onClearBadge }: ActivityFeedProps) {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getActivityFeed(projectId)
      .then(({ items }) => { if (!cancelled) setItems(items || []); })
      .catch(() => { if (!cancelled) setItems([]); })
      .finally(() => { if (!cancelled) { setLoading(false); onClearBadge(); } });
    return () => { cancelled = true };
  }, [projectId]);

  if (loading) return <div className="automata-loading" role="status"><span className="automata-spinner" aria-hidden="true" /><p>Loading activity…</p></div>;
  if (items.length === 0) return <div className="automata-empty"><p>No activity yet.</p></div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
      {items.map((item) => (
        <div key={item.id} style={{ border: '1px solid var(--color-border-soft)', borderRadius: 'var(--radius-md)', padding: '0.75rem', background: 'var(--color-bg-surface)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--color-text-tertiary)' }}>{new Date(item.created_at).toLocaleString()}</div>
          <div style={{ fontSize: '0.85rem', color: 'var(--color-text-primary)' }}>{item.summary}</div>
        </div>
      ))}
    </div>
  );
}
