/**
 * screens/SettingsScreen.tsx
 * Settings screen — AI mode, appearance, about panel.
 */
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { defaultContainer, defaultItem } from '../components/ui/VariantHelpers'
import { Settings, Cpu, Moon, Sun, Zap, Info, ExternalLink, Power, Clock } from 'lucide-react'
import GlassCard from '../components/ui/GlassCard'
import {
  getAutostart,
  setAutostart,
  getUsageSummary,
  setUsageTracking,
  type AutostartStatus,
  type UsageTrackerStatus,
} from '../lib/api'

interface SettingsProps {
  reasoningMode: string
  onModeChange: (mode: string) => void
  theme: 'dark' | 'light'
  onThemeToggle: () => void
}

const container = defaultContainer
const item = defaultItem

function Toggle({ checked, disabled, onChange, label }: { checked: boolean; disabled?: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      style={{
        width: 40, height: 22, borderRadius: 99, border: 'none', padding: 2, flexShrink: 0,
        background: checked ? 'var(--accent)' : 'var(--bg-hover)',
        cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1,
        transition: 'background var(--dur-fast) var(--ease-in-out)',
        display: 'flex', justifyContent: checked ? 'flex-end' : 'flex-start',
      }}
    >
      <motion.span layout transition={{ type: 'spring', stiffness: 500, damping: 32 }}
        style={{ width: 18, height: 18, borderRadius: '50%', background: '#fff', display: 'block' }} />
    </button>
  )
}

function BackgroundAgentCard() {
  const [autostart, setAutostartState] = useState<AutostartStatus | null>(null)
  const [tracking, setTracking] = useState<UsageTrackerStatus | null>(null)
  const [busy, setBusy] = useState<'autostart' | 'tracking' | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getAutostart().then(setAutostartState).catch(() => setAutostartState(null))
    getUsageSummary('today').then(s => setTracking(s.tracking ?? null)).catch(() => setTracking(null))
  }, [])

  const toggleAutostart = async (enabled: boolean) => {
    setBusy('autostart'); setError(null)
    try {
      const next = await setAutostart(enabled)
      setAutostartState(next)
      if (next.error) setError(next.error)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not change autostart')
    } finally { setBusy(null) }
  }

  const toggleTracking = async (enabled: boolean) => {
    setBusy('tracking'); setError(null)
    try { setTracking(await setUsageTracking(enabled)) } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not change tracking')
    } finally { setBusy(null) }
  }

  const trackingOn = !!tracking && tracking.running && !tracking.paused
  const rows = [
    {
      icon: Power,
      title: 'Start at sign-in',
      desc: autostart?.supported === false
        ? 'Only available on Windows.'
        : 'Runs the agent hidden in the background when you sign in to Windows, so capture and usage tracking never stop.',
      checked: !!autostart?.enabled,
      disabled: !autostart?.supported || busy === 'autostart',
      onChange: toggleAutostart,
    },
    {
      icon: Clock,
      title: 'Record app usage',
      desc: tracking && !tracking.supported
        ? 'Foreground-app tracking is Windows-only.'
        : 'Records which app has focus and for how long. Idle time is skipped. Stored only on this PC.',
      checked: trackingOn,
      disabled: !tracking?.supported || tracking?.disabled_by_env || busy === 'tracking',
      onChange: toggleTracking,
    },
  ]

  return (
    <GlassCard hoverable={false}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
        <Power size={16} color="var(--success)" />
        <h3 style={{ color: 'var(--text-primary)', fontSize: '0.9rem' }}>Background agent</h3>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
        {rows.map(r => (
          <div key={r.title} style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
            <r.icon size={15} color="var(--text-tertiary)" style={{ flexShrink: 0 }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>{r.title}</div>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-tertiary)', marginTop: 2 }}>{r.desc}</div>
            </div>
            <Toggle checked={r.checked} disabled={r.disabled} onChange={r.onChange} label={r.title} />
          </div>
        ))}
        {tracking?.db_path && (
          <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>
            Usage data: {tracking.db_path}
          </div>
        )}
        {error && <div style={{ fontSize: '0.75rem', color: 'var(--error)' }}>{error}</div>}
      </div>
    </GlassCard>
  )
}

export default function SettingsScreen({ reasoningMode, onModeChange, theme, onThemeToggle }: SettingsProps) {
  const activeMode = reasoningMode
  const handleMode = (m: string) => onModeChange(m)

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem', maxWidth: 680, width: '100%' }}>
      <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', stiffness: 220, damping: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.25rem' }}>
          <Settings size={20} color="var(--text-tertiary)" strokeWidth={2} />
          <h1>Settings</h1>
        </div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>Configure AUTOMATA's behavior and appearance.</p>
      </motion.div>

      <motion.div variants={container} initial="hidden" animate="show" style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        {/* AI Mode */}
        <motion.div variants={item}>
          <GlassCard hoverable>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
              <Cpu size={16} color="var(--ai-cyan)" />
              <h3 style={{ color: 'var(--text-primary)', fontSize: '0.9rem' }}>AI Reasoning Mode</h3>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {[
                { id: 'auto', label: 'Auto', desc: 'Configured cloud providers first (Groq, OpenRouter, Gemini, …), then Bedrock, then local Ollama.', icon: Zap, color: 'var(--accent)' },
                { id: 'local', label: 'Local only', desc: 'Uses Ollama only. Works offline. No API costs.', icon: Cpu, color: 'var(--success)' },
                { id: 'cloud', label: 'Cloud only', desc: 'Cloud providers and Bedrock only; never falls back to Ollama. Requires API keys.', icon: ExternalLink, color: 'var(--info)' },
              ].map(opt => {
                const Icon = opt.icon
                const isSelected = activeMode === opt.id
                return (
                  <motion.button
                    key={opt.id}
                    onClick={() => handleMode(opt.id)}
                    whileHover={{ x: 2 }}
                    whileTap={{ scale: 0.98 }}
                    transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                    style={{
                      display: 'flex', alignItems: 'flex-start', gap: '0.75rem',
                      padding: '0.75rem 1rem',
                      borderRadius: 'var(--r-md)',
                      border: `1px solid ${isSelected ? opt.color : 'var(--border-soft)'}`,
                      background: isSelected ? `${opt.color}10` : 'transparent',
                      cursor: 'pointer', textAlign: 'left', width: '100%',
                      transition: 'all var(--dur-fast) var(--ease-in-out)',
                    }}
                  >
                    <div style={{
                      width: 32, height: 32, borderRadius: 8, flexShrink: 0,
                      background: isSelected ? `${opt.color}20` : 'var(--bg-elevated)',
                      border: `1px solid ${isSelected ? opt.color : 'var(--border-soft)'}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <Icon size={15} color={isSelected ? opt.color : 'var(--text-tertiary)'} />
                    </div>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.85rem', color: isSelected ? opt.color : 'var(--text-primary)', marginBottom: '0.2rem' }}>{opt.label}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>{opt.desc}</div>
                    </div>
                    {isSelected && (
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        style={{ marginLeft: 'auto', width: 16, height: 16, borderRadius: '50%', background: opt.color, flexShrink: 0, alignSelf: 'center' }}
                      />
                    )}
                  </motion.button>
                )
              })}
            </div>
          </GlassCard>
        </motion.div>

        {/* Background agent */}
        <motion.div variants={item}>
          <BackgroundAgentCard />
        </motion.div>

        {/* Appearance */}
        <motion.div variants={item}>
          <GlassCard hoverable>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
              {theme === 'dark' ? <Moon size={16} color="var(--accent-2)" /> : <Sun size={16} color="var(--warning)" />}
              <h3 style={{ color: 'var(--text-primary)', fontSize: '0.9rem' }}>Appearance</h3>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              {(['dark', 'light'] as const).map(t => (
                <motion.button
                  key={t}
                  onClick={theme !== t ? onThemeToggle : undefined}
                  whileHover={{ y: -2, boxShadow: 'var(--shadow-md)' }}
                  whileTap={{ scale: 0.97 }}
                  style={{
                    flex: 1, padding: '1rem',
                    borderRadius: 'var(--r-md)',
                    border: `1px solid ${theme === t ? 'var(--accent)' : 'var(--border-soft)'}`,
                    background: theme === t ? 'var(--accent-muted)' : 'var(--bg-elevated)',
                    cursor: 'pointer',
                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem',
                    transition: 'all var(--dur-fast) var(--ease-in-out)',
                  }}
                >
                  {t === 'dark' ? <Moon size={20} color={theme === 'dark' ? 'var(--accent-2)' : 'var(--text-tertiary)'} /> : <Sun size={20} color={theme === 'light' ? 'var(--warning)' : 'var(--text-tertiary)'} />}
                  <span style={{ fontSize: '0.8rem', fontWeight: theme === t ? 600 : 400, color: theme === t ? 'var(--accent-2)' : 'var(--text-secondary)', textTransform: 'capitalize' }}>{t} mode</span>
                </motion.button>
              ))}
            </div>
          </GlassCard>
        </motion.div>

        {/* About */}
        <motion.div variants={item}>
          <GlassCard>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
              <Info size={16} color="var(--text-tertiary)" />
              <h3 style={{ color: 'var(--text-primary)', fontSize: '0.9rem' }}>About</h3>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {[
                { label: 'Version', value: 'v0.1.0' },
                { label: 'Frontend', value: 'React 19 + Tauri 2 + Framer Motion' },
                { label: 'Backend', value: 'FastAPI + CockroachDB + Multi-AI' },
                { label: 'Memory', value: 'Persistent vector memory (ANN search)' },
              ].map(row => (
                <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', padding: '0.4rem 0', borderBottom: '1px solid var(--border-soft)' }}>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>{row.label}</span>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{row.value}</span>
                </div>
              ))}
            </div>
          </GlassCard>
        </motion.div>
      </motion.div>
    </div>
  )
}
