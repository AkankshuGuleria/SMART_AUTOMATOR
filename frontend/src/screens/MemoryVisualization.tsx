/**
 * screens/MemoryVisualization.tsx
 * Tangible memory experience: timeline, interactive node graph, categories, semantic connections.
 * Data sourced from GET /projects/{projectId}/memory-graph.
 */
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Brain, GitCommit, Terminal as TerminalIcon, FileEdit,
  Lightbulb, Clock, Filter, ChevronDown, ChevronUp, Layers,
  CheckSquare,
} from 'lucide-react'
import GlassCard from '../components/ui/GlassCard'
import {
  getMemoryGraph,
  type MemoryGraphData,
  type MemoryGraphNode,
  type MemoryGraphEdge,
} from '../lib/api'

interface MemoryVisualizationProps {
  projectId?: string
}

type MemoryType = 'all' | 'commit' | 'file' | 'terminal' | 'decision' | 'architecture' | 'todo'

interface Memory {
  id: string
  type: 'commit' | 'file' | 'terminal' | 'decision' | 'architecture' | 'todo'
  content: string
  timestamp: string
  tags?: string[]
  connections?: string[]
}

interface GraphNode extends MemoryGraphNode {
  x: number
  y: number
  label: string
  type: string
}

const TYPE_CONFIG: Record<string, { icon: React.FC<{ size?: number }>; color: string; bg: string; label: string }> = {
  commit:       { icon: GitCommit,     color: 'var(--info)',      bg: 'var(--info-muted)',      label: 'Commit' },
  file:         { icon: FileEdit,      color: 'var(--success)',   bg: 'var(--success-muted)',   label: 'File Edit' },
  terminal:     { icon: TerminalIcon,  color: 'var(--warning)',   bg: 'var(--warning-muted)',   label: 'Terminal' },
  decision:     { icon: Lightbulb,     color: 'var(--accent-2)',  bg: 'var(--accent-muted)',    label: 'Decision' },
  architecture: { icon: Layers,        color: 'var(--ai-cyan)',   bg: 'var(--ai-cyan-muted)',   label: 'Architecture' },
  todo:         { icon: CheckSquare,   color: 'var(--warning)',   bg: 'var(--warning-muted)',   label: 'TODO' },
}

const CATEGORY_FILTERS: { id: MemoryType; label: string }[] = [
  { id: 'all',          label: 'All' },
  { id: 'decision',     label: 'Decisions' },
  { id: 'commit',       label: 'Commits' },
  { id: 'architecture', label: 'Architecture' },
  { id: 'file',         label: 'File Edits' },
  { id: 'terminal',     label: 'Terminal' },
  { id: 'todo',         label: 'TODOs' },
]

const TABLE_TO_TYPE: Record<string, Memory['type']> = {
  commits: 'commit',
  file_edits: 'file',
  architecture_notes: 'architecture',
  decision_log: 'decision',
  todos: 'todo',
}

function formatTimeAgo(ts: string | null | undefined): string {
  if (!ts) return 'Unknown time'
  try {
    const date = new Date(ts)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    const diffDays = Math.floor(diffHours / 24)
    if (diffHours < 1) return 'Just now'
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
    if (diffDays < 2) return 'Yesterday'
    if (diffDays < 7) return `${diffDays} days ago`
    return date.toLocaleDateString()
  } catch {
    return ts
  }
}

function generateCircularLayout(nodeIds: string[]): Record<string, { x: number; y: number }> {
  const centerX = 310
  const centerY = 220
  const radius = nodeIds.length > 1 ? 150 : 0
  const result: Record<string, { x: number; y: number }> = {}
  nodeIds.forEach((id, i) => {
    const angle = nodeIds.length === 1 ? 0 : (i / nodeIds.length) * 2 * Math.PI - Math.PI / 2
    result[id] = {
      x: centerX + Math.cos(angle) * radius,
      y: centerY + Math.sin(angle) * radius,
    }
  })
  return result
}

export default function MemoryVisualization({ projectId }: MemoryVisualizationProps) {
  const [memories, setMemories] = useState<Memory[]>([])
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([])
  const [graphEdges, setGraphEdges] = useState<MemoryGraphEdge[]>([])
  const [activeFilter, setActiveFilter] = useState<MemoryType>('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'timeline' | 'graph'>('timeline')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!projectId) {
      setLoading(false)
      setError(null)
      setMemories([])
      setGraphNodes([])
      setGraphEdges([])
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    getMemoryGraph(projectId)
      .then((data: MemoryGraphData) => {
        if (cancelled) return

        let edges = [...data.edges]

        // Add sibling edges: connect most recent commit to most recent file edit and most recent TODO
        const commits = data.nodes.filter((n) => n.table === 'commits')
        const fileEdits = data.nodes.filter((n) => n.table === 'file_edits')
        const todos = data.nodes.filter((n) => n.table === 'todos')

        if (commits.length > 0 && fileEdits.length > 0) {
          const mostRecentCommit = commits.reduce((latest, c) =>
            new Date(c.timestamp || 0) > new Date(latest.timestamp || 0) ? c : latest
          )
          const mostRecentFile = fileEdits.reduce((latest, f) =>
            new Date(f.timestamp || 0) > new Date(latest.timestamp || 0) ? f : latest
          )
          // Avoid duplicate edges
          const exists = edges.some(
            (e) =>
              (e.source === mostRecentCommit.id && e.target === mostRecentFile.id) ||
              (e.source === mostRecentFile.id && e.target === mostRecentCommit.id)
          )
          if (!exists) {
            edges.push({ source: mostRecentCommit.id, target: mostRecentFile.id, type: 'related' })
          }
        }

        if (commits.length > 0 && todos.length > 0) {
          const mostRecentCommit = commits.reduce((latest, c) =>
            new Date(c.timestamp || 0) > new Date(latest.timestamp || 0) ? c : latest
          )
          const mostRecentTodo = todos.reduce((latest, t) =>
            new Date(t.timestamp || 0) > new Date(latest.timestamp || 0) ? t : latest
          )
          const exists = edges.some(
            (e) =>
              (e.source === mostRecentCommit.id && e.target === mostRecentTodo.id) ||
              (e.source === mostRecentTodo.id && e.target === mostRecentCommit.id)
          )
          if (!exists) {
            edges.push({ source: mostRecentCommit.id, target: mostRecentTodo.id, type: 'related' })
          }
        }

        const connectionCounts: Record<string, string[]> = {}
        edges.forEach((e) => {
          connectionCounts[e.source] = [...(connectionCounts[e.source] || []), e.target]
          connectionCounts[e.target] = [...(connectionCounts[e.target] || []), e.source]
        })

        const mems: Memory[] = data.nodes.map((n) => ({
          id: n.id,
          type: TABLE_TO_TYPE[n.table] || 'architecture',
          content: n.content,
          timestamp: formatTimeAgo(n.timestamp),
          connections: connectionCounts[n.id]?.length > 0 ? connectionCounts[n.id] : undefined,
        }))
        setMemories(mems)

        const positions = generateCircularLayout(data.nodes.map((n) => n.id))
        const gNodes: GraphNode[] = data.nodes.map((n) => ({
          ...n,
          x: positions[n.id].x,
          y: positions[n.id].y,
          label: n.content.slice(0, 28),
          type: TABLE_TO_TYPE[n.table] || 'architecture',
        }))
        setGraphNodes(gNodes)
        setGraphEdges(edges)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load memory graph')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [projectId])

  const filtered = activeFilter === 'all'
    ? memories
    : memories.filter((m) => m.type === activeFilter)

  if (loading) {
    return (
      <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', stiffness: 220, damping: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
            <Brain size={22} color="var(--ai-purple)" strokeWidth={2} />
            <h1>Memory Visualization</h1>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
            Loading your memory graph…
          </p>
        </motion.div>
        <div className="automata-loading" role="status" aria-live="polite">
          <span className="automata-spinner" aria-hidden="true" />
          <p>Retrieving memories from persistent storage…</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', stiffness: 220, damping: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
            <Brain size={22} color="var(--ai-purple)" strokeWidth={2} />
            <h1>Memory Visualization</h1>
          </div>
        </motion.div>
        <div className="automata-error" role="alert">
          <p>Could not load memory graph.</p>
          <p>{error}</p>
        </div>
      </div>
    )
  }

  if (!projectId) {
    return (
      <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', stiffness: 220, damping: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
            <Brain size={22} color="var(--ai-purple)" strokeWidth={2} />
            <h1>Memory Visualization</h1>
          </div>
        </motion.div>
        <div className="automata-empty">
          <p>Select a project to view memory visualization.</p>
        </div>
      </div>
    )
  }

  if (memories.length === 0) {
    return (
      <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', stiffness: 220, damping: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
            <Brain size={22} color="var(--ai-purple)" strokeWidth={2} />
            <h1>Memory Visualization</h1>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
            0 memories captured · Knowledge graph · Semantic connections
          </p>
        </motion.div>
        <div className="automata-empty">
          <p>No memories captured yet. Start a session to begin building your knowledge graph.</p>
        </div>
      </div>
    )
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', stiffness: 220, damping: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
          <Brain size={22} color="var(--ai-purple)" strokeWidth={2} />
          <h1>Memory Visualization</h1>
        </div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
          {memories.length} memories captured · Knowledge graph · Semantic connections
        </p>
      </motion.div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid var(--border-soft)', paddingBottom: '0.5rem' }}>
        {[['timeline', 'Timeline'], ['graph', 'Knowledge Graph']].map(([id, label]) => (
          <button
            key={id}
            onClick={() => setActiveTab(id as 'timeline' | 'graph')}
            style={{
              padding: '0.4rem 1rem',
              borderRadius: 'var(--r-sm)',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.82rem',
              fontWeight: activeTab === id ? 600 : 400,
              background: activeTab === id ? 'var(--accent-muted)' : 'transparent',
              color: activeTab === id ? 'var(--accent-2)' : 'var(--text-tertiary)',
              transition: 'all var(--dur-fast) var(--ease-in-out)',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Category filters */}
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <Filter size={13} color="var(--text-tertiary)" />
        {CATEGORY_FILTERS.map(f => (
          <motion.button
            key={f.id}
            onClick={() => setActiveFilter(f.id)}
            whileTap={{ scale: 0.95 }}
            style={{
              padding: '0.3rem 0.75rem',
              borderRadius: 'var(--r-full)',
              border: '1px solid',
              borderColor: activeFilter === f.id ? 'var(--accent)' : 'var(--border-soft)',
              background: activeFilter === f.id ? 'var(--accent-muted)' : 'transparent',
              color: activeFilter === f.id ? 'var(--accent-2)' : 'var(--text-tertiary)',
              fontSize: '0.72rem',
              fontWeight: activeFilter === f.id ? 600 : 400,
              cursor: 'pointer',
              transition: 'all var(--dur-fast) var(--ease-in-out)',
            }}
          >
            {f.label}
          </motion.button>
        ))}
      </div>

      {/* ── Timeline Tab ─────────────────────────────────────────────────── */}
      <AnimatePresence mode="wait">
        {activeTab === 'timeline' && (
          <motion.div
            key="timeline"
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 12 }}
            transition={{ type: 'spring', stiffness: 300, damping: 28 }}
            style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', position: 'relative' }}
          >
            {/* Vertical line */}
            <div style={{
              position: 'absolute',
              left: 19,
              top: 20,
              bottom: 0,
              width: 2,
              background: 'linear-gradient(180deg, var(--accent) 0%, transparent 100%)',
              opacity: 0.3,
            }} />

            {filtered.map((mem, i) => {
              const cfg = TYPE_CONFIG[mem.type]
              const Icon = cfg.icon
              const isExpanded = expandedId === mem.id
              return (
                <motion.div
                  key={mem.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.06, type: 'spring', stiffness: 280, damping: 26 }}
                  style={{ display: 'flex', gap: '0.85rem', alignItems: 'flex-start' }}
                >
                  {/* Node dot */}
                    <div style={{ width: 38, height: 38, borderRadius: '50%', background: cfg.bg, border: `2px solid ${cfg.color}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, zIndex: 1, boxShadow: `0 0 12px ${cfg.color}40`, transition: 'box-shadow var(--dur-fast) var(--ease-in-out)' }}>
                      <span style={{ color: cfg.color, display: 'flex', alignItems: 'center' }}>
                        <Icon size={16} />
                      </span>
                    </div>

                  {/* Card */}
                  <GlassCard
                    hoverable
                    onClick={() => setExpandedId(isExpanded ? null : mem.id)}
                    style={{ flex: 1, cursor: 'pointer', borderLeft: `2px solid ${cfg.color}30` }}
                    padding="0.85rem"
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.5rem' }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem', flexWrap: 'wrap' }}>
                          <span style={{
                            fontSize: '0.62rem', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase',
                            padding: '0.1rem 0.5rem', borderRadius: 3,
                            background: cfg.bg, color: cfg.color,
                          }}>{cfg.label}</span>
                          <span style={{ display: 'flex', alignItems: 'center', gap: 2, fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>
                            <Clock size={10} />
                            {mem.timestamp}
                          </span>
                        </div>
                        <p style={{ fontSize: '0.82rem', color: isExpanded ? 'var(--text-primary)' : 'var(--text-secondary)', lineHeight: 1.5, transition: 'color var(--dur-fast) var(--ease-in-out)' }}>
                          {mem.content}
                        </p>
                      </div>
                      <div style={{ color: 'var(--text-tertiary)', flexShrink: 0 }}>
                        {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </div>
                    </div>

                    <AnimatePresence>
                      {isExpanded && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                          style={{ overflow: 'hidden' }}
                        >
                          <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-soft)' }}>
                            {mem.tags && (
                              <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
                                {mem.tags.map(t => (
                                  <span key={t} style={{
                                    fontSize: '0.65rem', padding: '0.1rem 0.45rem',
                                    borderRadius: 3, background: 'var(--bg-elevated)',
                                    border: '1px solid var(--border-soft)', color: 'var(--text-tertiary)',
                                  }}>#{t}</span>
                                ))}
                              </div>
                            )}
                            {mem.connections && mem.connections.length > 0 && (
                              <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)' }}>
                                Connected to {mem.connections.length} other memor{mem.connections.length > 1 ? 'ies' : 'y'}
                              </div>
                            )}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </GlassCard>
                </motion.div>
              )
            })}
          </motion.div>
        )}

        {/* ── Graph Tab ────────────────────────────────────────────────────── */}
        {activeTab === 'graph' && (
          <motion.div
            key="graph"
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 280, damping: 28 }}
          >
            <GlassCard hoverable style={{ minHeight: 440, position: 'relative', overflow: 'hidden' }}>
              {/* Ambient background glow */}
              <div style={{
                position: 'absolute', inset: 0,
                background: 'radial-gradient(ellipse at 50% 50%, rgba(108,79,255,0.06) 0%, transparent 70%)',
                pointerEvents: 'none',
              }} />

              {graphEdges.length === 0 ? (
                <div style={{
                  position: 'absolute',
                  inset: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--text-tertiary)',
                  fontSize: '0.9rem',
                  textAlign: 'center',
                }}>
                  Not enough data yet
                </div>
              ) : (
                <>
                  <svg
                    width="100%"
                    height="440"
                    viewBox="0 0 620 440"
                    style={{ position: 'absolute', inset: 0 }}
                  >
                    {/* Edges */}
                    {graphEdges.map((edge, i) => {
                      const from = graphNodes.find(n => n.id === edge.source)
                      const to   = graphNodes.find(n => n.id === edge.target)
                      if (!from || !to) return null
                      const isHovered = hoveredNode === edge.source || hoveredNode === edge.target
                      return (
                        <motion.line
                          key={i}
                          x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                          stroke={isHovered ? 'var(--accent)' : 'var(--border-hard)'}
                          strokeWidth={isHovered ? 2 : 1.25}
                          strokeDasharray={isHovered ? undefined : '4 4'}
                          opacity={isHovered ? 0.95 : 0.75}
                          animate={{ opacity: isHovered ? 0.95 : 0.75 }}
                          transition={{ duration: 0.2 }}
                        />
                      )
                    })}
                  </svg>

                  {/* Nodes */}
                  {graphNodes.map((node) => {
                    const cfg = TYPE_CONFIG[node.type] || TYPE_CONFIG['architecture']
                    const Icon = cfg.icon
                    const isHovered = hoveredNode === node.id
                    return (
                      <motion.div
                        key={node.id}
                        initial={{ scale: 0, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={{ type: 'spring', stiffness: 260, damping: 24, delay: Math.random() * 0.3 }}
                        onHoverStart={() => setHoveredNode(node.id)}
                        onHoverEnd={() => setHoveredNode(null)}
                        style={{
                          position: 'absolute',
                          left: node.x - 22,
                          top: node.y - 22,
                          width: 44, height: 44,
                          zIndex: 2,
                        }}
                      >
                        <motion.div
                          whileHover={{ scale: 1.25 }}
                          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                          style={{
                            width: '100%', height: '100%',
                            borderRadius: '50%',
                            background: cfg.bg,
                            border: `2px solid ${cfg.color}`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            cursor: 'pointer',
                            boxShadow: isHovered ? `0 0 20px ${cfg.color}80` : `0 0 8px ${cfg.color}40`,
                            transition: 'box-shadow var(--dur-base) var(--ease-in-out)',
                          }}
                        >
                          <span style={{ color: cfg.color, display: 'flex' }}><Icon size={18} /></span>
                        </motion.div>
                        <AnimatePresence>
                          {isHovered && (
                            <motion.div
                              initial={{ opacity: 0, y: 6, scale: 0.9 }}
                              animate={{ opacity: 1, y: 0, scale: 1 }}
                              exit={{ opacity: 0, y: 6, scale: 0.9 }}
                              transition={{ type: 'spring', stiffness: 380, damping: 28 }}
                              style={{
                                position: 'absolute',
                                bottom: '110%', left: '50%', transform: 'translateX(-50%)',
                                background: 'var(--bg-frosted)',
                                backdropFilter: 'var(--blur-md)',
                                border: '1px solid var(--border-soft)',
                                borderRadius: 'var(--r-sm)',
                                padding: '0.35rem 0.6rem',
                                whiteSpace: 'nowrap',
                                fontSize: '0.72rem',
                                color: 'var(--text-primary)',
                                boxShadow: 'var(--shadow-lg)',
                                zIndex: 10,
                              }}
                            >
                              {node.label}
                              <span style={{ marginLeft: 6, fontSize: '0.62rem', color: cfg.color }}>{cfg.label}</span>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </motion.div>
                    )
                  })}

                  {/* Legend */}
                  <div style={{
                    position: 'absolute', bottom: 12, right: 16,
                    display: 'flex', gap: '0.6rem', flexWrap: 'wrap', justifyContent: 'flex-end',
                  }}>
                    {Object.entries(TYPE_CONFIG).map(([type, cfg]) => (
                      <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <span style={{ width: 8, height: 8, borderRadius: '50%', background: cfg.color }} />
                        <span style={{ fontSize: '0.62rem', color: 'var(--text-tertiary)' }}>{cfg.label}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </GlassCard>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
