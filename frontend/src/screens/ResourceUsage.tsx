/**
 * screens/ResourceUsage.tsx
 * Live system resources + time-spent-on-apps + developer activity.
 */
import { useState } from 'react'
import { defaultContainer, defaultItem } from '../components/ui/VariantHelpers'
import { motion } from 'framer-motion'
import { Cpu, HardDrive, Wifi, Battery, Clock, Code2, MoreHorizontal } from 'lucide-react'
import GlassCard from '../components/ui/GlassCard'
import ProgressRing from '../components/ui/ProgressRing'
import { ATLineChart, ATAreaChart, ATBarChart, ATDonutChart } from '../components/ui/AnimatedChart'

type TimeRange = 'today' | 'week' | 'month'

// Mock data — real data via future Tauri system_info plugin
const SYSTEM = {
  cpu:  { current: 34, history: [22, 28, 41, 34, 29, 38, 34, 40, 31, 34] },
  ram:  { current: 67, used: '10.7 GB', total: '16 GB' },
  disk: { current: 58, used: '348 GB', total: '512 GB' },
  net:  { up: '2.3 MB/s', down: '8.1 MB/s' },
  battery: { level: 84, charging: true },
}

const CPU_HISTORY = Array.from({ length: 20 }, (_, i) => ({
  t: `${i}m`,
  cpu: Math.round(20 + Math.random() * 35 + Math.sin(i * 0.5) * 10),
  mem: Math.round(55 + Math.random() * 15 + Math.sin(i * 0.3) * 8),
}))

const APP_TIME = [
  { app: 'VS Code',      hours: 4.2, color: '#22d3ee', category: 'Coding' },
  { app: 'Chrome',       hours: 1.8, color: '#a78bfa', category: 'Browsing' },
  { app: 'Terminal',     hours: 1.4, color: '#10b981', category: 'Coding' },
  { app: 'Slack',        hours: 0.9, color: '#f59e0b', category: 'Communication' },
  { app: 'Figma',        hours: 0.6, color: '#ec4899', category: 'Design' },
  { app: 'Spotify',      hours: 0.4, color: '#6c4fff', category: 'Other' },
]

const ACTIVITY_TIMELINE = Array.from({ length: 24 }, (_, h) => ({
  hour: `${h}:00`,
  coding: h >= 9 && h <= 18 ? Math.round(Math.random() * 50 + 10) : Math.round(Math.random() * 10),
  browsing: h >= 8 && h <= 22 ? Math.round(Math.random() * 30) : 0,
  other: Math.round(Math.random() * 15),
}))

const WEEKLY_CODING = [
  { day: 'Mon', hours: 5.2 }, { day: 'Tue', hours: 3.8 }, { day: 'Wed', hours: 6.1 },
  { day: 'Thu', hours: 4.5 }, { day: 'Fri', hours: 4.2 }, { day: 'Sat', hours: 1.1 }, { day: 'Sun', hours: 0.8 },
]

const CATEGORY_DONUT = [
  { name: 'Coding', value: 56, color: '#22d3ee' },
  { name: 'Browsing', value: 20, color: '#a78bfa' },
  { name: 'Communication', value: 12, color: '#f59e0b' },
  { name: 'Other', value: 12, color: '#6c4fff' },
]

const container = defaultContainer
const item = defaultItem

export default function ResourceUsage() {
  const [range, setRange] = useState<TimeRange>('today')

  const totalCodingHours = APP_TIME.filter(a => a.category === 'Coding').reduce((s, a) => s + a.hours, 0)
  const totalHours = APP_TIME.reduce((s, a) => s + a.hours, 0)
  const focusScore = Math.round((totalCodingHours / totalHours) * 100)

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', stiffness: 220, damping: 24 }}>
        <h1 style={{ marginBottom: '0.25rem' }}>Resources & Usage</h1>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
          Live system metrics and how your time is being spent.
        </p>
      </motion.div>

      {/* Time filter */}
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        {(['today', 'week', 'month'] as TimeRange[]).map(r => (
          <motion.button
            key={r}
            onClick={() => setRange(r)}
            whileTap={{ scale: 0.95 }}
            style={{
              padding: '0.4rem 0.9rem',
              borderRadius: 'var(--r-full)',
              border: '1px solid',
              borderColor: range === r ? 'var(--accent)' : 'var(--border-soft)',
              background: range === r ? 'var(--accent-muted)' : 'transparent',
              color: range === r ? 'var(--accent-2)' : 'var(--text-tertiary)',
              fontSize: '0.78rem',
              fontWeight: range === r ? 600 : 400,
              cursor: 'pointer',
              fontFamily: 'var(--font-sans)',
              textTransform: 'capitalize',
              transition: 'all var(--dur-fast) var(--ease-in-out)',
            }}
          >
            {r}
          </motion.button>
        ))}
      </div>

      {/* ── A. Live System Resources ──────────────────────────────────────── */}
      <motion.div variants={container} initial="hidden" animate="show">
        <h2 style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-tertiary)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '0.75rem' }}>
          Live System
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.85rem' }}>
          {/* CPU */}
          <motion.div variants={item}>
            <GlassCard hoverable>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Cpu size={14} color="var(--ai-cyan)" />
                  <span style={{ fontSize: '0.78rem', fontWeight: 600 }}>CPU</span>
                </div>
                <ProgressRing value={SYSTEM.cpu.current} size={40} stroke={4} color="var(--ai-cyan)" glow label={`${SYSTEM.cpu.current}%`} />
              </div>
              <div style={{ height: 50, marginTop: 8 }}>
                <ATLineChart
                  data={SYSTEM.cpu.history.map((v, i) => ({ t: i, cpu: v }))}
                  lines={[{ key: 'cpu', color: 'var(--ai-cyan)' }]}
                  xKey="t"
                  height={50}
                  gridLines={false}
                />
              </div>
            </GlassCard>
          </motion.div>

          {/* RAM */}
          <motion.div variants={item}>
            <GlassCard hoverable>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <HardDrive size={14} color="var(--accent-2)" />
                  <span style={{ fontSize: '0.78rem', fontWeight: 600 }}>RAM</span>
                </div>
                <ProgressRing value={SYSTEM.ram.current} size={40} stroke={4} color="var(--accent-2)" glow label={`${SYSTEM.ram.current}%`} />
              </div>
              <p style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginTop: 4 }}>
                {SYSTEM.ram.used} / {SYSTEM.ram.total}
              </p>
            </GlassCard>
          </motion.div>

          {/* Disk */}
          <motion.div variants={item}>
            <GlassCard hoverable>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <HardDrive size={14} color="var(--warning)" />
                  <span style={{ fontSize: '0.78rem', fontWeight: 600 }}>Disk</span>
                </div>
                <ProgressRing value={SYSTEM.disk.current} size={40} stroke={4} color="var(--warning)" label={`${SYSTEM.disk.current}%`} />
              </div>
              <p style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginTop: 4 }}>
                {SYSTEM.disk.used} / {SYSTEM.disk.total}
              </p>
            </GlassCard>
          </motion.div>

          {/* Network */}
          <motion.div variants={item}>
            <GlassCard hoverable>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.75rem' }}>
                <Wifi size={14} color="var(--success)" />
                <span style={{ fontSize: '0.78rem', fontWeight: 600 }}>Network</span>
              </div>
              <div style={{ display: 'flex', gap: '1rem' }}>
                <div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>↑ Upload</div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--success)', fontFamily: 'var(--font-mono)' }}>{SYSTEM.net.up}</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>↓ Download</div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--info)', fontFamily: 'var(--font-mono)' }}>{SYSTEM.net.down}</div>
                </div>
              </div>
            </GlassCard>
          </motion.div>

          {/* Battery */}
          <motion.div variants={item}>
            <GlassCard hoverable>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Battery size={14} color="var(--success)" />
                  <span style={{ fontSize: '0.78rem', fontWeight: 600 }}>Battery</span>
                </div>
                <ProgressRing value={SYSTEM.battery.level} size={40} stroke={4} color="var(--success)" label={`${SYSTEM.battery.level}%`} />
              </div>
              <span style={{ fontSize: '0.7rem', color: 'var(--success)', marginTop: 4, display: 'block' }}>
                {SYSTEM.battery.charging ? '⚡ Charging' : 'On battery'}
              </span>
            </GlassCard>
          </motion.div>
        </div>
      </motion.div>

      {/* CPU + Memory trend */}
      <GlassCard hoverable>
        <ATLineChart
          title="CPU & Memory Trend (last 20 min)"
          data={CPU_HISTORY}
          lines={[
            { key: 'cpu', color: 'var(--ai-cyan)', label: 'CPU %' },
            { key: 'mem', color: 'var(--accent-2)', label: 'RAM %' },
          ]}
          xKey="t"
          height={140}
        />
      </GlassCard>

      {/* ── B. Time-Spent-on-Apps ─────────────────────────────────────────── */}
      <div>
        <h2 style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-tertiary)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '0.75rem' }}>
          Time Spent · Apps
        </h2>

        {/* Summary stat cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
          {[
            { label: 'Total Screen Time', value: `${totalHours.toFixed(1)}h`, icon: Clock, color: 'var(--text-primary)' },
            { label: 'Coding Time', value: `${totalCodingHours.toFixed(1)}h`, icon: Code2, color: 'var(--ai-cyan)' },
            { label: 'Focus Score', value: `${focusScore}%`, icon: Cpu, color: 'var(--success)' },
            { label: 'Idle Time', value: '0.8h', icon: MoreHorizontal, color: 'var(--text-tertiary)' },
          ].map(s => {
            const Icon = s.icon
            return (
              <GlassCard key={s.label} padding="0.85rem" hoverable>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.3rem' }}>
                  <Icon size={13} color={s.color} />
                  <span style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)' }}>{s.label}</span>
                </div>
                <span style={{ fontSize: '1.3rem', fontWeight: 700, color: s.color, fontFamily: 'var(--font-display)' }}>{s.value}</span>
              </GlassCard>
            )
          })}
        </div>

        {/* App bar chart + Donut */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '1rem', alignItems: 'start' }}>
          <GlassCard hoverable>
            <ATBarChart
              title="Top Apps by Time (hours)"
              data={APP_TIME.map(a => ({ app: a.app, hours: a.hours }))}
              bars={APP_TIME.slice(0, 1).map(() => ({ key: 'hours', color: 'var(--accent)' }))}
              xKey="app"
              height={180}
            />
          </GlassCard>
          <GlassCard padding="1.25rem" style={{ minWidth: 200 }}>
            <ATDonutChart
              title="By Category"
              data={CATEGORY_DONUT}
              size={160}
              label={`${focusScore}%`}
              sublabel="focus"
            />
          </GlassCard>
        </div>
      </div>

      {/* Activity timeline */}
      <GlassCard hoverable>
        <ATAreaChart
          title="App Activity Timeline (today)"
          data={ACTIVITY_TIMELINE}
          areas={[
            { key: 'coding', color: 'var(--ai-cyan)', label: 'Coding' },
            { key: 'browsing', color: 'var(--accent-2)', label: 'Browsing' },
            { key: 'other', color: 'var(--warning)', label: 'Other' },
          ]}
          xKey="hour"
          height={160}
          stacked
        />
      </GlassCard>

      {/* ── C. Developer Activity ─────────────────────────────────────────── */}
      <div>
        <h2 style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-tertiary)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '0.75rem' }}>
          Developer Activity
        </h2>
        <GlassCard hoverable>
          <ATBarChart
            title="Coding Hours per Day (this week)"
            data={WEEKLY_CODING}
            bars={[{ key: 'hours', color: 'var(--ai-cyan)', label: 'Hours' }]}
            xKey="day"
            height={160}
          />
        </GlassCard>
      </div>
    </div>
  )
}
