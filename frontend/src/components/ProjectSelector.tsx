/**
 * components/ProjectSelector.tsx — AUTOMATA project workspace hub.
 *
 * Owns:    Project registration (folder browse), project list with stats,
 *          active project switching, and inline ProjectInsights display.
 * Never:   Must not talk directly to CockroachDB or Bedrock — all data
 *          flows through lib/api.ts.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Folder, Plus, FolderOpen, GitCommit, CheckSquare,
  Clock, User, Trash2,
  ChevronUp, Search, X,
} from 'lucide-react'
import GlassCard from './ui/GlassCard'
import {
  registerProject,
  getProjectAnalytics,
  type Project,
} from '../lib/api'
import ProjectInsights from '../screens/ProjectInsights'

interface ProjectSelectorProps {
  activeProjectId: string | null
  projects: Project[]
  onProjectSelect: (id: string | null) => void
  onProjectAdded: (project: Project) => void
  onProjectsChange: (projects: Project[]) => void
}

interface ProjectStats {
  commits: number
  edits: number
  todos: { pending: number; completed: number; total: number }
  sessions: number
  timeSeconds: number
}

const FOLDER_NAME_RE = /([^/\\]+)[/\\]?$/

function deriveNameFromPath(repoPath: string): string {
  if (!repoPath) return 'Untitled Project'
  const match = repoPath.match(FOLDER_NAME_RE)
  const base = match ? match[1] : repoPath
  return base.replace(/[-_]/g, ' ') || repoPath
}

function formatDuration(seconds: number): string {
  if (seconds <= 0) return '—'
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  if (hours > 0) return `${hours}h ${mins}m`
  return `${mins}m`
}

export default function ProjectSelector({
  activeProjectId,
  projects: initialProjects,
  onProjectSelect,
  onProjectAdded,
  onProjectsChange,
}: ProjectSelectorProps) {
  const [projects, setProjects] = useState<Project[]>(initialProjects)
  const [addOpen, setAddOpen] = useState(false)
  const [folderPath, setFolderPath] = useState('')
  const [projectName, setProjectName] = useState('')
  const [registering, setRegistering] = useState(false)
  const [registerError, setRegisterError] = useState<string | null>(null)
  const [statsMap, setStatsMap] = useState<Record<string, ProjectStats>>({})
  const [statsLoading, setStatsLoading] = useState<Record<string, boolean>>({})
  const [searchQuery, setSearchQuery] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Sync with parent projects prop
  useEffect(() => {
    setProjects(initialProjects)
  }, [initialProjects])

  const loadStats = useCallback(async (projectId: string) => {
    if (statsMap[projectId] || statsLoading[projectId]) return
    setStatsLoading(prev => ({ ...prev, [projectId]: true }))
    try {
      const { analytics } = await getProjectAnalytics(projectId)
      const stats: ProjectStats = {
        commits: analytics.commits_over_time?.reduce((s, c) => s + c.count, 0) || 0,
        edits: analytics.file_edits_over_time?.reduce((s, c) => s + c.count, 0) || 0,
        todos: analytics.todo_stats,
        sessions: analytics.session_stats.total_sessions,
        timeSeconds: analytics.session_stats.total_time_seconds,
      }
      setStatsMap(prev => ({ ...prev, [projectId]: stats }))
    } catch {
      setStatsMap(prev => ({ ...prev, [projectId]: {
        commits: 0, edits: 0, todos: { pending: 0, completed: 0, total: 0 },
        sessions: 0, timeSeconds: 0,
      }}))
    } finally {
      setStatsLoading(prev => ({ ...prev, [projectId]: false }))
    }
  }, [statsMap, statsLoading])

  // Auto-load stats for visible projects
  useEffect(() => {
    projects.forEach(p => loadStats(p.id))
  }, [projects, loadStats])

  const filteredProjects = searchQuery.trim()
    ? projects.filter(p =>
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.repo_path.toLowerCase().includes(searchQuery.toLowerCase()),
      )
    : projects

  const handleFolderSelect = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      const path = files[0].webkitRelativePath || files[0].name
      const dirPath = path.split('/')[0] || e.target.value
      setFolderPath(dirPath || e.target.value)
      setProjectName(deriveNameFromPath(dirPath || e.target.value))
    }
    e.target.value = ''
  }

  const handleRegister = async () => {
    if (!folderPath.trim()) {
      setRegisterError('Please enter a folder path')
      return
    }
    setRegistering(true)
    setRegisterError(null)
    try {
      const { project } = await registerProject(
        projectName || deriveNameFromPath(folderPath),
        folderPath,
      )
      onProjectAdded(project)
      setProjects(prev => [...prev, project])
      setAddOpen(false)
      setFolderPath('')
      setProjectName('')
    } catch (err) {
      setRegisterError(err instanceof Error ? err.message : 'Repository path not found on this machine. Check the path and try again.')
    } finally {
      setRegistering(false)
    }
  }

  const handleSwitchProject = (id: string) => {
    onProjectSelect(id)
  }

  const handleRemoveProject = (id: string) => {
    // Remove locally — note: no delete API endpoint yet
    setProjects(prev => prev.filter(p => p.id !== id))
    onProjectsChange(projects.filter(p => p.id !== id))
    setStatsMap(prev => {
      const copy = { ...prev }
      delete copy[id]
      return copy
    })
    if (activeProjectId === id) {
      onProjectSelect(null)
    }
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem' }}>
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 220, damping: 24 }}
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1.25rem',
          flexWrap: 'wrap',
          gap: '0.75rem',
        }}
      >
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <FolderOpen size={22} color="var(--accent)" />
            Project Workspace
          </h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)', marginTop: '0.25rem' }}>
            Register a project, switch between workspaces, and view live analytics.
          </p>
        </div>
        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
          onClick={() => setAddOpen(!addOpen)}
          style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            padding: '0.55rem 1rem',
            borderRadius: 'var(--r-md)',
            border: '1px solid var(--border-soft)',
            background: addOpen ? 'var(--bg-elevated)' : 'var(--bg-glass)',
            color: 'var(--text-secondary)',
            fontSize: '0.8rem',
            cursor: 'pointer',
          }}
        >
          {addOpen ? <ChevronUp size={14} /> : <Plus size={14} color="var(--accent)" />}
          Add Project
        </motion.button>
      </motion.div>

      {/* Add Project form */}
      <AnimatePresence>
        {addOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0, y: -8 }}
            animate={{ opacity: 1, height: 'auto', y: 0 }}
            exit={{ opacity: 0, height: 0, y: -8 }}
            transition={{ type: 'spring', stiffness: 300, damping: 26 }}
          >
            <GlassCard style={{ marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Folder size={16} color="var(--accent)" />
                  <h3 style={{ margin: 0, fontSize: '0.85rem', fontWeight: 600 }}>
                    Register New Project
                  </h3>
                </div>

                <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'flex-end' }}>
                  <div style={{ flex: 1 }}>
                    <label style={{
                      display: 'block', fontSize: '0.65rem',
                      color: 'var(--text-tertiary)', marginBottom: '0.3rem',
                      fontFamily: 'var(--font-mono)',
                    }}>
                      Folder Path
                    </label>
                    <input
                      type="text"
                      value={folderPath}
                      onChange={e => {
                        setFolderPath(e.target.value)
                        if (!projectName && e.target.value) {
                          setProjectName(deriveNameFromPath(e.target.value))
                        } else if (!e.target.value) {
                          setProjectName('')
                        }
                      }}
                      placeholder="e.g. C:\Users\dev\my-project"
                      style={{
                        width: '100%', padding: '0.6rem 0.9rem',
                        background: 'var(--bg-elevated)',
                        border: '1px solid var(--border-soft)',
                        borderRadius: 'var(--r-md)',
                        color: 'var(--text-primary)',
                        fontFamily: 'var(--font-mono)', fontSize: '0.8rem',
                        outline: 'none',
                      }}
                      onFocus={e => e.target.select()}
                    />
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  onChange={handleFileChange}
                  style={{ display: 'none' }}
                  aria-label="Browse folder"
                  {...({ directory: 'true', webkitdirectory: 'true' } as any)}
                />
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={handleFolderSelect}
                    style={{
                      padding: '0.6rem 0.9rem',
                      borderRadius: 'var(--r-md)',
                      border: '1px solid var(--border-soft)',
                      background: 'var(--bg-elevated)',
                      color: 'var(--text-secondary)',
                      fontSize: '0.8rem',
                      cursor: 'pointer',
                      marginBottom: 22,
                    }}
                  >
                    Browse
                  </motion.button>
                </div>

                <div>
                  <label style={{
                    display: 'block', fontSize: '0.65rem',
                    color: 'var(--text-tertiary)', marginBottom: '0.3rem',
                  }}>
                    Project Name
                  </label>
                  <input
                    type="text"
                    value={projectName}
                    onChange={e => setProjectName(e.target.value)}
                    placeholder="Auto-derived from folder name"
                    style={{
                      width: '100%', padding: '0.6rem 0.9rem',
                      background: 'var(--bg-elevated)',
                      border: '1px solid var(--border-soft)',
                      borderRadius: 'var(--r-md)',
                      color: 'var(--text-primary)',
                      fontFamily: 'var(--font-sans)', fontSize: '0.85rem',
                      outline: 'none',
                    }}
                  />
                </div>

                {registerError && (
                  <div style={{
                    padding: '0.5rem 0.75rem',
                    background: 'var(--error-muted)',
                    borderRadius: 'var(--r-sm)',
                    color: 'var(--error)',
                    fontSize: '0.75rem',
                  }}>
                    {registerError}
                  </div>
                )}

                <div style={{ display: 'flex', gap: '0.6rem', justifyContent: 'flex-end' }}>
                  <motion.button
                    whileHover={{ scale: 1.03 }}
                    whileTap={{ scale: 0.97 }}
                    onClick={() => setAddOpen(false)}
                    style={{
                      padding: '0.5rem 1rem',
                      borderRadius: 'var(--r-sm)',
                      border: '1px solid var(--border-soft)',
                      background: 'transparent',
                      color: 'var(--text-tertiary)',
                      fontSize: '0.8rem', cursor: 'pointer',
                    }}
                  >
                    Cancel
                  </motion.button>
                  <motion.button
                    whileHover={{ scale: 1.03 }}
                    whileTap={{ scale: 0.97 }}
                    onClick={handleRegister}
                    disabled={registering || !folderPath.trim()}
                    style={{
                      padding: '0.5rem 1.2rem',
                      borderRadius: 'var(--r-sm)',
                      border: 'none',
                      background: registering
                        ? 'var(--bg-elevated)'
                        : 'linear-gradient(135deg, var(--accent) 0%, #8b6fff 100%)',
                      color: registering ? 'var(--text-tertiary)' : '#fff',
                      fontSize: '0.8rem', fontWeight: 600,
                      cursor: registering ? 'default' : 'pointer',
                      opacity: registering ? 0.6 : 1,
                    }}
                  >
                    {registering ? 'Registering…' : 'Register'}
                  </motion.button>
                </div>
              </div>
            </GlassCard>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Search */}
      <div style={{ position: 'relative', marginBottom: '1rem' }}>
        <Search size={14} style={{
          position: 'absolute', left: 10, top: '50%',
          transform: 'translateY(-50%)', color: 'var(--text-tertiary)',
        }} />
        <input
          type="text"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          placeholder="Search projects…"
          style={{
            width: '100%', padding: '0.5rem 0.85rem 0.5rem 2rem',
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-soft)',
            borderRadius: 'var(--r-md)',
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-sans)', fontSize: '0.82rem',
            outline: 'none',
          }}
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            style={{
              position: 'absolute', right: 8, top: '50%',
              transform: 'translateY(-50%)',
              background: 'none', border: 'none',
              color: 'var(--text-tertiary)', cursor: 'pointer',
              padding: 2,
            }}
          >
            <X size={12} />
          </button>
        )}
      </div>

      {/* Project list */}
      {filteredProjects.length === 0 ? (
        <div className="automata-empty">
          <Folder size={32} color="var(--text-disabled)" />
          <h3>No projects registered</h3>
          <p>Click "Add Project" above to get started.</p>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
          gap: '0.85rem',
          marginBottom: '1.5rem',
        }}>
          {filteredProjects.map((proj) => {
            const isActive = proj.id === activeProjectId
            const stats = statsMap[proj.id]
            const loading = statsLoading[proj.id]

            return (
              <motion.div
                key={proj.id}
                initial={{ opacity: 0, scale: 0.97 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ type: 'spring', stiffness: 300, damping: 26 }}
                whileHover={{ y: -2 }}
              >
                <GlassCard
                  hoverable
                  onClick={() => handleSwitchProject(proj.id)}
                  style={{
                    border: `1px solid ${isActive
                      ? 'var(--accent)'
                      : 'var(--border-glass)'}`,
                    background: isActive
                      ? 'var(--accent-muted)'
                      : 'var(--bg-glass)',
                    cursor: 'pointer',
                    position: 'relative',
                  }}
                >
                  <div style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.5rem',
                  }}>
                    <div style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      justifyContent: 'space-between',
                      gap: '0.5rem',
                    }}>
                      <div style={{
                        width: 32, height: 32, borderRadius: 8,
                        background: 'linear-gradient(135deg, var(--accent) 0%, var(--ai-cyan) 100%)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        flexShrink: 0,
                      }}>
                        <Folder size={16} color="#fff" />
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          fontSize: '0.85rem', fontWeight: 600,
                          color: 'var(--text-primary)',
                          display: 'flex', alignItems: 'center', gap: '0.3rem',
                        }}>
                          {proj.name}
                          {isActive && (
                            <span style={{
                              fontSize: '0.58rem',
                              background: 'var(--accent)',
                              color: '#fff',
                              padding: '0.1rem 0.4rem',
                              borderRadius: 'var(--r-full)',
                              fontWeight: 700,
                            }}>ACTIVE</span>
                          )}
                        </div>
                        <div style={{
                          fontSize: '0.68rem', color: 'var(--text-tertiary)',
                          fontFamily: 'var(--font-mono)', marginTop: '0.15rem',
                          wordBreak: 'break-all',
                        }}>
                          {proj.repo_path}
                        </div>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          handleRemoveProject(proj.id)
                        }}
                        style={{
                          background: 'none', border: 'none',
                          color: 'var(--text-tertiary)',
                          padding: 4, cursor: 'pointer',
                          opacity: 0.6,
                        }}
                        title="Remove from list"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>

                    {/* Quick stats */}
                    {loading && (
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)' }}>
                        Loading stats…
                      </div>
                    )}
                    {!loading && stats && (
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        gap: '0.4rem',
                        fontSize: '0.72rem',
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                          <GitCommit size={11} color="var(--info)" />
                          <span style={{ color: 'var(--text-secondary)' }}>{stats.commits} commits</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                          <CheckSquare size={11} color="var(--accent-2)" />
                          <span style={{ color: 'var(--text-secondary)' }}>
                            {stats.todos.completed}/{stats.todos.total} done
                          </span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                          <Clock size={11} color="var(--warning)" />
                          <span style={{ color: 'var(--text-secondary)' }}>{stats.sessions} sessions</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                          <User size={11} color="var(--ai-cyan)" />
                          <span style={{ color: 'var(--text-tertiary)' }}>{formatDuration(stats.timeSeconds)}</span>
                        </div>
                      </div>
                    )}

                    {isActive && (
                      <div style={{
                        fontSize: '0.62rem',
                        color: 'var(--accent-2)',
                        fontFamily: 'var(--font-mono)',
                        marginTop: '0.2rem',
                      }}>
                        ↑ Active project — analytics below
                      </div>
                    )}
                  </div>
                </GlassCard>
              </motion.div>
            )
          })}
        </div>
      )}

      {/* Active project insights */}
      <AnimatePresence>
        {activeProjectId && (
          <motion.div
            key="insights"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            transition={{ type: 'spring', stiffness: 220, damping: 24 }}
          >
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              marginBottom: '0.75rem',
            }}>
              <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Active Project Analytics</h2>
              <button
                onClick={() => handleSwitchProject('')}
                style={{
                  padding: '0.3rem 0.7rem',
                  borderRadius: 'var(--r-full)',
                  border: '1px solid var(--border-soft)',
                  background: 'transparent',
                  color: 'var(--text-tertiary)',
                  fontSize: '0.72rem',
                  cursor: 'pointer',
                }}
              >
                ← Switch project
              </button>
            </div>
            <ProjectInsights projectId={activeProjectId} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
