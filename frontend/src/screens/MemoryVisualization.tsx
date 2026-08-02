/**
 * screens/MemoryVisualization.tsx
 * Tangible memory experience: timeline, interactive node graph, categories, semantic connections.
 */
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Brain, GitCommit, Terminal as TerminalIcon, FileEdit,
  Lightbulb, Clock, Filter, ChevronDown, ChevronUp, Layers,
} from 'lucide-react'
import GlassCard from '../components/ui/GlassCard'

type MemoryType = 'all' | 'commit' | 'file' | 'terminal' | 'decision' | 'architecture'

interface Memory {
  id: string
  type: 'commit' | 'file' | 'terminal' | 'decision' | 'architecture'
  content: string
  timestamp: string
  tags?: string[]
  connections?: string[]
}

const MOCK_MEMORIES: Memory[] = [
  { id: 'm1', type: 'decision', content: 'Chose CockroachDB vector search over Pinecone to keep single-DB architecture. Reduced ops overhead and cost for the hackathon scope.', timestamp: '2 hours ago', tags: ['architecture', 'database'], connections: ['m3', 'm5'] },
  { id: 'm2', type: 'commit', content: 'feat: add vector retrieval pipeline with ANN search. Implemented cosine similarity ranking over 1536-dim embeddings.', timestamp: '5 hours ago', tags: ['memory', 'search'], connections: ['m1'] },
  { id: 'm3', type: 'architecture', content: 'Decided to use Bedrock + Groq + Ollama as fallback chain. Primary: Ollama (local speed), fallback: Groq (fast cloud), emergency: Bedrock.', timestamp: 'Yesterday', tags: ['ai', 'architecture'], connections: ['m1', 'm4'] },
  { id: 'm4', type: 'terminal', content: 'uv run python main.py — backend starts on :8000 with hot-reload. FastAPI + uvicorn with CORS for localhost:1420 (Tauri).', timestamp: 'Yesterday', tags: ['devops'] },
  { id: 'm5', type: 'file', content: 'backend/ai/bedrock_client.py modified: Added invoke_embedding() with multi-provider support. Falls back through 6 providers.', timestamp: '2 days ago', tags: ['ai', 'embeddings'], connections: ['m2'] },
  { id: 'm6', type: 'decision', content: 'Chose Tauri over Electron for the desktop shell — 10x smaller binary, Rust backend, no Chromium bundled. Native system calls for workspace restore.', timestamp: '3 days ago', tags: ['architecture', 'desktop'] },
  { id: 'm7', type: 'commit', content: 'fix: handle null embeddings gracefully in retrieval pipeline. Added fallback to keyword search when vector is None.', timestamp: '3 days ago', tags: ['bug', 'memory'] },
]

const TYPE_CONFIG: Record<string, { icon: React.FC<{ size?: number }>; color: string; bg: string; label: string }> = {
  commit:       { icon: GitCommit,     color: 'var(--info)',     bg: 'var(--info-muted)',     label: 'Commit' },
  file:         { icon: FileEdit,      color: 'var(--success)',  bg: 'var(--success-muted)',  label: 'File Edit' },
  terminal:     { icon: TerminalIcon,  color: 'var(--warning)',  bg: 'var(--warning-muted)',  label: 'Terminal' },
  decision:     { icon: Lightbulb,     color: 'var(--accent-2)', bg: 'var(--accent-muted)',   label: 'Decision' },
  architecture: { icon: Layers,        color: 'var(--ai-cyan)',  bg: 'var(--ai-cyan-muted)',  label: 'Architecture' },
}

const CATEGORY_FILTERS: { id: MemoryType; label: string }[] = [
  { id: 'all',          label: 'All' },
  { id: 'decision',     label: 'Decisions' },
  { id: 'commit',       label: 'Commits' },
  { id: 'architecture', label: 'Architecture' },
  { id: 'file',         label: 'File Edits' },
  { id: 'terminal',     label: 'Terminal' },
]

// Simple 2D node graph (CSS-based, no Three.js dependency for now)
const NODES = [
  { id: 'm1', label: 'CockroachDB Decision', type: 'decision', x: 260, y: 120 },
  { id: 'm2', label: 'Vector Retrieval', type: 'commit', x: 420, y: 220 },
  { id: 'm3', label: 'AI Provider Chain', type: 'architecture', x: 140, y: 250 },
  { id: 'm4', label: 'Backend Startup', type: 'terminal', x: 80, y: 380 },
  { id: 'm5', label: 'Embedding Pipeline', type: 'file', x: 380, y: 350 },
  { id: 'm6', label: 'Tauri Choice', type: 'decision', x: 520, y: 100 },
  { id: 'm7', label: 'Null Fix', type: 'commit', x: 480, y: 300 },
]

const EDGES = [
  { from: 'm1', to: 'm2' }, { from: 'm1', to: 'm3' }, { from: 'm3', to: 'm4' },
  { from: 'm2', to: 'm5' }, { from: 'm5', to: 'm7' }, { from: 'm1', to: 'm5' },
]

export default function MemoryVisualization() {
  const [activeFilter, setActiveFilter] = useState<MemoryType>('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'timeline' | 'graph'>('timeline')

  const filtered = activeFilter === 'all' ? MOCK_MEMORIES : MOCK_MEMORIES.filter(m => m.type === activeFilter)

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', stiffness: 220, damping: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
          <Brain size={22} color="var(--ai-purple)" strokeWidth={2} />
          <h1>Memory Visualization</h1>
        </div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
          {MOCK_MEMORIES.length} memories captured · Knowledge graph · Semantic connections
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
                          <span style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>
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
                                🔗 Connected to {mem.connections.length} other memor{mem.connections.length > 1 ? 'ies' : 'y'}
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

              <svg
                width="100%"
                height="440"
                viewBox="0 0 620 440"
                style={{ position: 'absolute', inset: 0 }}
              >
                {/* Edges */}
                {EDGES.map((edge, i) => {
                  const from = NODES.find(n => n.id === edge.from)!
                  const to   = NODES.find(n => n.id === edge.to)!
                  const isHovered = hoveredNode === edge.from || hoveredNode === edge.to
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
              {NODES.map((node) => {
                const cfg = TYPE_CONFIG[node.type]
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
            </GlassCard>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
