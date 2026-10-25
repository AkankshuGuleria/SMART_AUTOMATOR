/**
 * screens/ResourceUsage.tsx
 * Live host resources (CPU / GPU / RAM / disk / network), background app-usage
 * analytics, and agent health. Every number comes from the local backend.
 */
import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Cpu, MemoryStick, HardDrive, Gauge, Wifi, BatteryCharging, Battery,
  Activity, Clock, Target, Shuffle, Trophy, Pause, Play, Zap, Shield, Monitor,
} from 'lucide-react'
import GlassCard from '../components/ui/GlassCard'
import ProgressRing from '../components/ui/ProgressRing'
import { ATAreaChart, ATBarChart, ATDonutChart } from '../components/ui/AnimatedChart'
import { usePolling } from '../lib/usePolling'
import {
  getSystemMetrics,
  getUsageSummary,
  getUsageTimeline,
  setUsageTracking,
  getHealth,
  getToolStatus,
  getLiveMetrics,
  type SystemMetrics,
  type UsageSummary,
  type UsageTimeline,
  type UsageRange,
  type HealthStatus,
  type ToolStatus,
  type LiveMetrics,
} from '../lib/api'

type Tab = 'system' | 'usage' | 'agent'

const CATEGORY_COLORS: Record<string, string> = {
  Development: '#6c4fff',
  Browser: '#22d3ee',
  Communication: '#f59e0b',
  Productivity: '#10b981',
  'AI Assistants': '#a855f7',
  Entertainment: '#ec4899',
  Other: '#64748b',
}
const categoryColor = (c: string) => CATEGORY_COLORS[c] ?? CATEGORY_COLORS.Other

// ─── formatting ──────────────────────────────────────────────────────────────

function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))
  if (s < 60) return `${s}s`
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

function formatRate(bps: number): string {
  if (bps >= 1024 ** 2) return `${(bps / 1024 ** 2).toFixed(1)} MB/s`
  if (bps >= 1024) return `${(bps / 1024).toFixed(0)} KB/s`
  return `${Math.round(bps)} B/s`
}

function formatMb(mb: number): string {
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${Math.round(mb)} MB`
}

function loadColor(pct: number): string {
  if (pct >= 90) return 'var(--error)'
  if (pct >= 70) return 'var(--warning)'
  return 'var(--success)'
}

// ─── small building blocks ───────────────────────────────────────────────────

const sectionTitle: React.CSSProperties = {
  fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-tertiary)',
  letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '0.75rem',
}

function MetricCard({ icon: Icon, label, value, sub, pct, color }: {
  icon: typeof Cpu; label: string; value: string; sub?: string; pct: number | null; color?: string
}) {
  const ringColor = color ?? (pct === null ? 'var(--text-disabled)' : loadColor(pct))
  return (
    <GlassCard padding="1rem" hoverable={false}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem' }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.4rem' }}>
            <Icon size={14} color={ringColor} />
            <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', fontWeight: 500 }}>{label}</span>
          </div>
          <div style={{ fontSize: '1.45rem', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-display)', fontVariantNumeric: 'tabular-nums' }}>
            {value}
          </div>
          {sub && (
            <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {sub}
            </div>
          )}
        </div>
        <ProgressRing value={pct ?? 0} size={52} stroke={5} color={ringColor} animate={false} />
      </div>
    </GlassCard>
  )
}

function Stat({ icon: Icon, label, value, sub }: { icon: typeof Cpu; label: string; value: string; sub?: string }) {
  return (
    <GlassCard padding="0.9rem" hoverable={false}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.35rem' }}>
        <Icon size={13} color="var(--accent-2)" />
        <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{label}</span>
      </div>
      <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-display)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: '0.66rem', color: 'var(--text-tertiary)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{sub}</div>}
    </GlassCard>
  )
}

function Notice({ children, tone = 'muted' }: { children: React.ReactNode; tone?: 'muted' | 'error' }) {
  return (
    <div style={{
      padding: '0.75rem 1rem', borderRadius: 'var(--r-md)', fontSize: '0.8rem',
      background: tone === 'error' ? 'var(--error-muted)' : 'var(--bg-elevated)',
      color: tone === 'error' ? 'var(--error)' : 'var(--text-tertiary)',
      border: '1px solid var(--border-soft)',
    }}>
      {children}
    </div>
  )
}

// ─── System tab ──────────────────────────────────────────────────────────────

function SystemTab() {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null)
  const [error, setError] = useState<string | null>(null)

  usePolling(async () => {
    try {
      setMetrics(await getSystemMetrics(true))
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Backend unreachable')
    }
  }, 2000)

  const history = useMemo(() => (metrics?.history ?? []).map(p => ({
    time: new Date(p.t * 1000).toLocaleTimeString([], { minute: '2-digit', second: '2-digit' }),
    CPU: p.cpu,
    RAM: p.ram,
    ...(p.gpu !== null ? { GPU: p.gpu } : {}),
  })), [metrics?.history])

  if (error && !metrics) return <Notice tone="error">Could not load system metrics: {error}</Notice>
  if (!metrics) return <Notice>Reading system sensors…</Notice>
  if (!metrics.available) return <Notice>System metrics unavailable: {metrics.reason}</Notice>

  const { cpu, memory, gpu, disk, network, battery } = metrics
  const g = gpu?.devices?.[0]
  const hasGpu = !!g
  const processes = metrics.processes ?? []
  const maxProcCpu = Math.max(1, ...processes.map(p => p.cpu_percent))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '0.85rem' }}>
        <MetricCard
          icon={Cpu} label="CPU" value={`${cpu?.percent.toFixed(0)}%`} pct={cpu?.percent ?? 0}
          sub={`${cpu?.cores_physical ?? '?'} cores / ${cpu?.cores_logical} threads${cpu?.frequency_mhz ? ` · ${(cpu.frequency_mhz / 1000).toFixed(2)} GHz` : ''}`}
        />
        <MetricCard
          icon={Monitor} label="GPU"
          value={hasGpu && g.utilization_percent !== null ? `${g.utilization_percent}%` : '—'}
          pct={hasGpu ? g.utilization_percent : null}
          sub={hasGpu
            ? `${g.name ?? 'GPU'}${g.temperature_c !== null ? ` · ${g.temperature_c}°C` : ''}`
            : (gpu?.reason ?? 'No supported GPU found')}
        />
        <MetricCard
          icon={Gauge} label="GPU memory"
          value={hasGpu && g.memory_used_mb !== null ? formatMb(g.memory_used_mb) : '—'}
          pct={hasGpu ? g.memory_percent : null}
          sub={hasGpu && g.memory_total_mb ? `of ${formatMb(g.memory_total_mb)}${g.power_watts !== null ? ` · ${g.power_watts} W` : ''}` : 'NVIDIA GPUs only'}
        />
        <MetricCard
          icon={MemoryStick} label="RAM" value={`${memory?.percent.toFixed(0)}%`} pct={memory?.percent ?? 0}
          sub={`${memory?.used_gb.toFixed(1)} / ${memory?.total_gb.toFixed(1)} GB · swap ${memory?.swap_percent.toFixed(0)}%`}
        />
        <MetricCard
          icon={HardDrive} label={`Disk ${disk?.mount ?? ''}`}
          value={disk?.percent !== null && disk?.percent !== undefined ? `${disk.percent.toFixed(0)}%` : '—'}
          pct={disk?.percent ?? null}
          sub={`R ${formatRate(disk?.read_bps ?? 0)} · W ${formatRate(disk?.write_bps ?? 0)}`}
        />
      </div>

      <GlassCard hoverable={false}>
        <ATAreaChart
          title="Live load (last few minutes)"
          data={history}
          areas={[
            { key: 'CPU', color: '#6c4fff', label: 'CPU %' },
            { key: 'RAM', color: '#10b981', label: 'RAM %' },
            ...(hasGpu ? [{ key: 'GPU', color: '#22d3ee', label: 'GPU %' }] : []),
          ]}
          xKey="time"
          height={190}
          animate={false}
          yDomain={[0, 100]}
        />
      </GlassCard>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.85rem' }}>
        <GlassCard hoverable={false}>
          <h4 style={sectionTitle}>CPU threads</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(34px, 1fr))', gap: 6 }}>
            {(cpu?.per_core ?? []).map((v, i) => (
              <div key={i} title={`Thread ${i}: ${v}%`} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
                <div style={{ width: '100%', height: 42, background: 'var(--bg-elevated)', borderRadius: 4, overflow: 'hidden', display: 'flex', alignItems: 'flex-end' }}>
                  <div style={{ width: '100%', height: `${Math.max(2, v)}%`, background: loadColor(v), transition: 'height 0.4s var(--ease-out)' }} />
                </div>
                <span style={{ fontSize: '0.58rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{Math.round(v)}</span>
              </div>
            ))}
          </div>
        </GlassCard>

        <GlassCard hoverable={false}>
          <h4 style={sectionTitle}>Network & power</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.82rem' }}>
            <Row icon={Wifi} label="Download" value={formatRate(network?.recv_bps ?? 0)} />
            <Row icon={Wifi} label="Upload" value={formatRate(network?.sent_bps ?? 0)} />
            {battery
              ? <Row icon={battery.plugged_in ? BatteryCharging : Battery} label="Battery" value={`${battery.percent}%${battery.plugged_in ? ' · charging' : ''}`} />
              : <Row icon={Battery} label="Battery" value="No battery" />}
            <Row icon={Clock} label="System uptime" value={formatDuration(metrics.uptime_seconds ?? 0)} />
          </div>
        </GlassCard>
      </div>

      <GlassCard hoverable={false}>
        <h4 style={sectionTitle}>Top processes</h4>
        {processes.length === 0 ? (
          <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>Scanning processes…</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 70px 90px', gap: '0.75rem', fontSize: '0.66rem', color: 'var(--text-tertiary)', padding: '0 0.5rem 0.35rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              <span>Process</span><span style={{ textAlign: 'right' }}>CPU</span><span style={{ textAlign: 'right' }}>Memory</span>
            </div>
            {processes.map(p => (
              <div key={p.name} style={{ position: 'relative', display: 'grid', gridTemplateColumns: '1fr 70px 90px', gap: '0.75rem', alignItems: 'center', padding: '0.4rem 0.5rem', borderRadius: 6, fontSize: '0.78rem' }}>
                <div style={{ position: 'absolute', inset: 0, width: `${(p.cpu_percent / maxProcCpu) * 100}%`, background: 'var(--accent-muted)', borderRadius: 6, pointerEvents: 'none' }} />
                <span style={{ position: 'relative', color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {p.name}{p.count > 1 && <span style={{ color: 'var(--text-tertiary)' }}> ×{p.count}</span>}
                </span>
                <span style={{ position: 'relative', textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{p.cpu_percent.toFixed(1)}%</span>
                <span style={{ position: 'relative', textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{formatMb(p.memory_mb)}</span>
              </div>
            ))}
          </div>
        )}
      </GlassCard>
    </div>
  )
}

function Row({ icon: Icon, label, value }: { icon: typeof Cpu; label: string; value: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <span style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', color: 'var(--text-secondary)' }}>
        <Icon size={13} color="var(--text-tertiary)" />{label}
      </span>
      <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{value}</span>
    </div>
  )
}

// ─── App usage tab ───────────────────────────────────────────────────────────

function UsageTab() {
  const [range, setRange] = useState<UsageRange>('today')
  const [summary, setSummary] = useState<UsageSummary | null>(null)
  const [timeline, setTimeline] = useState<UsageTimeline | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [toggling, setToggling] = useState(false)

  const load = async () => {
    try {
      const [s, t] = await Promise.all([
        getUsageSummary(range),
        range === 'today' ? getUsageTimeline() : Promise.resolve(null),
      ])
      setSummary(s)
      setTimeline(t)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Backend unreachable')
    }
  }
  usePolling(load, 15000, [range])

  const tracking = summary?.tracking
  const toggleTracking = async () => {
    if (!tracking) return
    setToggling(true)
    try {
      await setUsageTracking(tracking.paused || !tracking.running)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not change tracking')
    } finally {
      setToggling(false)
    }
  }

  const buckets = useMemo(() => {
    if (!summary) return []
    if (summary.range === 'today') {
      return summary.hourly.map(h => ({ label: `${h.hour}`, minutes: Math.round(h.seconds / 60) }))
    }
    return summary.daily.map(d => ({
      label: new Date(`${d.day}T00:00:00`).toLocaleDateString([], summary.range === 'week' ? { weekday: 'short' } : { day: 'numeric', month: 'short' }),
      minutes: Math.round(d.seconds / 60),
    }))
  }, [summary])

  const donut = useMemo(() => (summary?.categories ?? []).map(c => ({
    name: c.category, value: c.seconds, color: categoryColor(c.category),
  })), [summary])

  const status = !tracking ? null
    : !tracking.supported ? { label: 'Not supported on this OS', color: 'var(--text-tertiary)' }
    : tracking.disabled_by_env ? { label: 'Disabled by configuration', color: 'var(--text-tertiary)' }
    : tracking.paused ? { label: 'Paused', color: 'var(--warning)' }
    : !tracking.running ? { label: 'Not running', color: 'var(--error)' }
    : tracking.idle ? { label: 'Idle — not counting', color: 'var(--warning)' }
    : { label: 'Recording', color: 'var(--success)' }

  const top = summary?.apps?.[0]
  const maxApp = Math.max(1, ...(summary?.apps ?? []).map(a => a.seconds))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap' }}>
        <Segmented value={range} onChange={v => setRange(v as UsageRange)} options={[
          { value: 'today', label: 'Today' }, { value: 'week', label: '7 days' }, { value: 'month', label: '30 days' },
        ]} />
        {status && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: status.color }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: status.color, boxShadow: status.label === 'Recording' ? `0 0 8px ${status.color}` : undefined }} />
              {status.label}
            </span>
            {tracking?.current && !tracking.paused && (
              <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
                Now: <span style={{ color: 'var(--text-primary)' }}>{tracking.current.app}</span> · {formatDuration(Date.now() / 1000 - tracking.current.since)}
              </span>
            )}
            {tracking?.supported && !tracking.disabled_by_env && (
              <button onClick={toggleTracking} disabled={toggling} style={pillButton}>
                {tracking.paused || !tracking.running ? <Play size={12} /> : <Pause size={12} />}
                {tracking.paused || !tracking.running ? 'Resume' : 'Pause'}
              </button>
            )}
          </div>
        )}
      </div>

      {error && <Notice tone="error">Could not load usage data: {error}</Notice>}
      {!summary && !error && <Notice>Loading usage…</Notice>}

      {summary && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.75rem' }}>
            <Stat icon={Clock} label="Active time" value={formatDuration(summary.total_seconds)} sub="idle time excluded" />
            <Stat icon={Target} label="Development focus" value={`${summary.focus_percent}%`} sub="share of active time" />
            <Stat icon={Trophy} label="Top app" value={top?.app ?? '—'} sub={top ? formatDuration(top.seconds) : 'no data yet'} />
            <Stat icon={Shuffle} label="App switches" value={String(summary.app_switches)} />
            <Stat icon={Activity} label="Longest session" value={summary.longest_session ? formatDuration(summary.longest_session.seconds) : '—'} sub={summary.longest_session?.app} />
          </div>

          {summary.total_seconds === 0 ? (
            <Notice>
              No app usage recorded for this period yet. Usage is recorded while the AUTOMATA backend runs —
              enable “Start at sign-in” in Settings to keep it running in the background.
            </Notice>
          ) : (
            <>
              {timeline && timeline.segments.length > 0 && <TimelineStrip timeline={timeline} />}

              <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.6fr) minmax(240px, 1fr)', gap: '0.85rem' }}>
                <GlassCard hoverable={false}>
                  <h4 style={sectionTitle}>Time by app</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
                    {summary.apps.slice(0, 12).map(a => (
                      <div key={a.app} title={a.top_title || a.app}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: 3, gap: '0.5rem' }}>
                          <span style={{ color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                            <span style={{ width: 8, height: 8, borderRadius: 2, background: categoryColor(a.category), flexShrink: 0 }} />
                            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.app}</span>
                          </span>
                          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', flexShrink: 0 }}>
                            {formatDuration(a.seconds)} <span style={{ color: 'var(--text-tertiary)' }}>{a.percent}%</span>
                          </span>
                        </div>
                        <div style={{ height: 6, background: 'var(--bg-elevated)', borderRadius: 99, overflow: 'hidden' }}>
                          <motion.div
                            initial={false}
                            animate={{ width: `${(a.seconds / maxApp) * 100}%` }}
                            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                            style={{ height: '100%', background: categoryColor(a.category), borderRadius: 99 }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </GlassCard>
                <GlassCard hoverable={false} style={{ display: 'flex', justifyContent: 'center' }}>
                  <ATDonutChart
                    title="By category"
                    data={donut}
                    size={170}
                    label={formatDuration(summary.total_seconds)}
                    sublabel="active"
                  />
                </GlassCard>
              </div>

              <GlassCard hoverable={false}>
                <ATBarChart
                  title={summary.range === 'today' ? 'Active minutes by hour' : 'Active minutes by day'}
                  data={buckets}
                  bars={[{ key: 'minutes', color: '#6c4fff', label: 'Minutes' }]}
                  xKey="label"
                  height={170}
                  animate={false}
                />
              </GlassCard>
            </>
          )}
        </>
      )}
    </div>
  )
}

function TimelineStrip({ timeline }: { timeline: UsageTimeline }) {
  const segs = timeline.segments
  const start = segs[0].start
  const end = Math.max(segs[segs.length - 1].end, start + 60)
  const span = end - start
  const fmt = (t: number) => new Date(t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return (
    <GlassCard hoverable={false}>
      <h4 style={sectionTitle}>Today’s timeline</h4>
      <div style={{ position: 'relative', height: 26, background: 'var(--bg-elevated)', borderRadius: 6, overflow: 'hidden' }}>
        {segs.map((s, i) => (
          <div
            key={i}
            title={`${s.app} · ${fmt(s.start)}–${fmt(s.end)} · ${formatDuration(s.seconds)}${s.title ? `\n${s.title}` : ''}`}
            style={{
              position: 'absolute', top: 0, bottom: 0,
              left: `${((s.start - start) / span) * 100}%`,
              width: `max(1px, ${((s.end - s.start) / span) * 100}%)`,
              background: categoryColor(s.category),
              opacity: 0.85,
            }}
          />
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: '0.66rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
        <span>{fmt(start)}</span><span>{fmt(end)}</span>
      </div>
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginTop: '0.6rem' }}>
        {Object.entries(CATEGORY_COLORS).filter(([c]) => segs.some(s => s.category === c)).map(([c, color]) => (
          <span key={c} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: color }} />{c}
          </span>
        ))}
      </div>
    </GlassCard>
  )
}

// ─── Agent tab ───────────────────────────────────────────────────────────────

function AgentTab({ projectId }: { projectId?: string }) {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [tools, setTools] = useState<ToolStatus[]>([])
  const [live, setLive] = useState<LiveMetrics | null>(null)
  const [loaded, setLoaded] = useState(false)

  usePolling(async () => {
    const [h, t, m] = await Promise.all([
      getHealth().catch(() => null),
      getToolStatus().catch(() => ({ tools: [] as ToolStatus[] })),
      projectId ? getLiveMetrics(projectId).catch(() => null) : Promise.resolve(null),
    ])
    setHealth(h)
    setTools(t.tools ?? [])
    setLive(m)
    setLoaded(true)
  }, 10000, [projectId])

  const apiOk = health?.api === 'ok'
  const dbOk = health?.db?.db === 'connected'
  const services = [
    { label: 'Backend API', ok: apiOk, detail: apiOk ? 'Online' : 'Offline', icon: Zap },
    { label: 'CockroachDB', ok: dbOk, detail: dbOk ? 'Connected' : (health?.db?.reason || 'Disconnected'), icon: Activity },
    { label: 'Reasoning', ok: live?.agent.reasoning_backend === 'available', detail: live ? (live.agent.reasoning_backend === 'available' ? 'Provider reachable' : 'No provider reachable') : 'Select a project', icon: Shield },
    { label: 'Embeddings', ok: health?.embedding === 'configured', detail: health?.embedding === 'configured' ? 'Configured' : 'Not configured', icon: Cpu },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.85rem' }}>
        {services.map(s => (
          <GlassCard key={s.label} padding="1rem" hoverable={false}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.4rem' }}>
              <s.icon size={14} color={s.ok ? 'var(--success)' : 'var(--warning)'} />
              <span style={{ fontSize: '0.78rem', fontWeight: 600 }}>{s.label}</span>
            </div>
            <span style={{ fontSize: '0.8rem', color: s.ok ? 'var(--success)' : 'var(--warning)' }}>{s.detail}</span>
          </GlassCard>
        ))}
      </div>

      {live && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem' }}>
          <Stat icon={Clock} label="Agent uptime" value={formatDuration(live.agent.uptime_seconds)} />
          <Stat icon={Activity} label="Events / hour" value={String(live.memory.events_last_hour)} />
          <Stat icon={Zap} label="Metrics latency" value={`${Math.round(live.agent.api_latency_ms)} ms`} />
          <Stat icon={Shield} label="Failed commands" value={String(live.memory.failed_commands)} />
          <Stat icon={Target} label="TODOs done" value={`${live.memory.todos_done}/${live.memory.todos_done + live.memory.todos_pending}`} />
        </div>
      )}

      <div>
        <h4 style={sectionTitle}>Developer tools</h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem' }}>
          {tools.map(tool => (
            <GlassCard key={tool.name} padding="0.85rem" hoverable={false}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.3rem' }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: tool.available ? 'var(--success)' : 'var(--error)' }} />
                <span style={{ fontSize: '0.78rem', fontWeight: 600 }}>{tool.name}</span>
              </div>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                {tool.available ? (tool.version || 'available') : 'not found'}
              </span>
            </GlassCard>
          ))}
          {loaded && tools.length === 0 && <Notice>No tool data available.</Notice>}
        </div>
      </div>

      {live?.performance.module_health && live.performance.module_health.length > 0 && (
        <div>
          <h4 style={sectionTitle}>Module readiness</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '0.75rem' }}>
            {live.performance.module_health.map(m => (
              <GlassCard key={m.name} padding="0.9rem" hoverable={false}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '0.4rem' }}>
                  <span style={{ fontWeight: 600 }}>{m.name}</span>
                  <span style={{ color: 'var(--accent-2)', fontWeight: 600 }}>{Math.round(m.pct)}%</span>
                </div>
                <div style={{ height: 4, background: 'var(--bg-elevated)', borderRadius: 99, overflow: 'hidden', marginBottom: '0.4rem' }}>
                  <div style={{ height: '100%', width: `${Math.min(100, Math.max(0, m.pct))}%`, background: 'linear-gradient(90deg, var(--accent), var(--ai-cyan))' }} />
                </div>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)' }}>{m.basis}</div>
              </GlassCard>
            ))}
          </div>
        </div>
      )}
      {!projectId && <Notice>Select a project to see memory and module metrics.</Notice>}
    </div>
  )
}

// ─── shell ───────────────────────────────────────────────────────────────────

const pillButton: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 5,
  padding: '0.3rem 0.75rem', borderRadius: 'var(--r-full)',
  border: '1px solid var(--border-soft)', background: 'var(--bg-elevated)',
  color: 'var(--text-secondary)', fontSize: '0.74rem', cursor: 'pointer', fontFamily: 'var(--font-sans)',
}

function Segmented({ value, onChange, options }: {
  value: string; onChange: (v: string) => void; options: { value: string; label: string }[]
}) {
  return (
    <div role="tablist" style={{ display: 'inline-flex', gap: 2, padding: 3, background: 'var(--bg-elevated)', border: '1px solid var(--border-soft)', borderRadius: 'var(--r-full)' }}>
      {options.map(o => (
        <button
          key={o.value}
          role="tab"
          aria-selected={value === o.value}
          onClick={() => onChange(o.value)}
          style={{
            padding: '0.35rem 0.9rem', borderRadius: 'var(--r-full)', border: 'none',
            background: value === o.value ? 'var(--accent)' : 'transparent',
            color: value === o.value ? '#fff' : 'var(--text-secondary)',
            fontSize: '0.78rem', fontWeight: value === o.value ? 600 : 500,
            cursor: 'pointer', fontFamily: 'var(--font-sans)',
            transition: 'background var(--dur-fast) var(--ease-in-out), color var(--dur-fast) var(--ease-in-out)',
          }}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

interface ResourceUsageProps {
  projectId?: string
}

export default function ResourceUsage({ projectId }: ResourceUsageProps) {
  const [tab, setTab] = useState<Tab>('system')
  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ marginBottom: '0.25rem' }}>Resources</h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
            Live machine load, where your time goes, and agent health.
          </p>
        </div>
        <Segmented value={tab} onChange={v => setTab(v as Tab)} options={[
          { value: 'system', label: 'System' },
          { value: 'usage', label: 'App usage' },
          { value: 'agent', label: 'Agent' },
        ]} />
      </div>
      {tab === 'system' && <SystemTab />}
      {tab === 'usage' && <UsageTab />}
      {tab === 'agent' && <AgentTab projectId={projectId} />}
    </div>
  )
}
