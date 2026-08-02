/**
 * components/ui/AnimatedChart.tsx
 * Shared Recharts wrapper with AUTOMATA design tokens, animated entrance, and responsive container.
 */
import {
  ResponsiveContainer,
  LineChart, Line,
  AreaChart, Area,
  BarChart, Bar,
  PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts'
import { motion } from 'framer-motion'

// Custom Tooltip
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function AutomataTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--bg-frosted)',
      backdropFilter: 'var(--blur-md)',
      border: '1px solid var(--border-soft)',
      borderRadius: 'var(--r-md)',
      padding: '0.6rem 0.9rem',
      boxShadow: 'var(--shadow-lg)',
      fontSize: '0.78rem',
      color: 'var(--text-primary)',
    }}>
      {label && <div style={{ color: 'var(--text-tertiary)', marginBottom: 4, fontFamily: 'var(--font-mono)' }}>{label}</div>}
      {payload.map((p: { name: string; value: any; color: string }, i: number) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: p.color, flexShrink: 0 }} />
          <span style={{ color: 'var(--text-secondary)' }}>{p.name}:</span>
          <span style={{ fontWeight: 600 }}>{p.value}</span>
        </div>
      ))}
    </div>
  )
}

interface ChartBaseProps {
  data: Record<string, unknown>[]
  height?: number
  title?: string
  className?: string
}

// ─── Line Chart ──────────────────────────────────────────────────────────────
interface LineChartProps extends ChartBaseProps {
  lines: { key: string; color: string; label?: string }[]
  xKey?: string
  gridLines?: boolean
}

export function ATLineChart({ data, lines, xKey = 'name', height = 200, title, gridLines = true }: LineChartProps) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}>
      {title && <h4 style={{ marginBottom: '0.75rem', color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase' }}>{title}</h4>}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
          {gridLines && <CartesianGrid strokeDasharray="3 3" stroke="var(--border-soft)" vertical={false} />}
          <XAxis dataKey={xKey} tick={{ fontSize: 10, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} />
          <Tooltip content={<AutomataTooltip />} />
          {lines.map(l => (
            <Line
              key={l.key}
              type="monotone"
              dataKey={l.key}
              name={l.label ?? l.key}
              stroke={l.color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 0 }}
              animationDuration={1200}
              animationEasing="ease-out"
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </motion.div>
  )
}

// ─── Area Chart ───────────────────────────────────────────────────────────────
interface AreaChartProps extends ChartBaseProps {
  areas: { key: string; color: string; label?: string }[]
  xKey?: string
  stacked?: boolean
}

export function ATAreaChart({ data, areas, xKey = 'name', height = 200, title, stacked = false }: AreaChartProps) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}>
      {title && <h4 style={{ marginBottom: '0.75rem', color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase' }}>{title}</h4>}
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
          <defs>
            {areas.map(a => (
              <linearGradient key={a.key} id={`grad-${a.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={a.color} stopOpacity={0.25} />
                <stop offset="100%" stopColor={a.color} stopOpacity={0.02} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-soft)" vertical={false} />
          <XAxis dataKey={xKey} tick={{ fontSize: 10, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} />
          <Tooltip content={<AutomataTooltip />} />
          {stacked && <Legend wrapperStyle={{ fontSize: 11, color: 'var(--text-secondary)' }} />}
          {areas.map(a => (
            <Area
              key={a.key}
              type="monotone"
              dataKey={a.key}
              name={a.label ?? a.key}
              stroke={a.color}
              fill={`url(#grad-${a.key})`}
              strokeWidth={2}
              stackId={stacked ? 'stack' : undefined}
              animationDuration={1200}
              animationEasing="ease-out"
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </motion.div>
  )
}

// ─── Bar Chart ────────────────────────────────────────────────────────────────
interface ATBarChartProps extends ChartBaseProps {
  bars: { key: string; color: string; label?: string }[]
  xKey?: string
  horizontal?: boolean
}

export function ATBarChart({ data, bars, xKey = 'name', height = 200, title, horizontal = false }: ATBarChartProps) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}>
      {title && <h4 style={{ marginBottom: '0.75rem', color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase' }}>{title}</h4>}
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} layout={horizontal ? 'vertical' : 'horizontal'} margin={{ top: 4, right: 4, bottom: 0, left: horizontal ? 60 : -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-soft)" horizontal={!horizontal} vertical={horizontal} />
          {horizontal
            ? <><YAxis dataKey={xKey} type="category" tick={{ fontSize: 10, fill: 'var(--text-secondary)' }} axisLine={false} tickLine={false} width={80} />
                <XAxis type="number" tick={{ fontSize: 10, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} /></>
            : <><XAxis dataKey={xKey} tick={{ fontSize: 10, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} /></>
          }
          <Tooltip content={<AutomataTooltip />} />
          {bars.map(b => (
            <Bar key={b.key} dataKey={b.key} name={b.label ?? b.key} fill={b.color} radius={[4, 4, 0, 0]} maxBarSize={32} animationDuration={1000} animationEasing="ease-out" />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </motion.div>
  )
}

// ─── Donut Chart ──────────────────────────────────────────────────────────────
interface DonutChartProps {
  data: { name: string; value: number; color: string }[]
  size?: number
  label?: string
  sublabel?: string
  title?: string
}

export function ATDonutChart({ data, size = 140, label, sublabel, title }: DonutChartProps) {
  const total = data.reduce((s, d) => s + d.value, 0)
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem' }}
    >
      {title && <h4 style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase' }}>{title}</h4>}
      <div style={{ position: 'relative' }}>
        <PieChart width={size} height={size}>
          <Pie
            data={data}
            cx={size / 2 - 4}
            cy={size / 2 - 4}
            innerRadius={size * 0.32}
            outerRadius={size * 0.46}
            dataKey="value"
            paddingAngle={3}
            animationBegin={0}
            animationDuration={1200}
          >
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Pie>
        </PieChart>
        {(label || sublabel) && (
          <div style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            {label && <span style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>{label}</span>}
            {sublabel && <span style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)', marginTop: 1 }}>{sublabel}</span>}
          </div>
        )}
      </div>
      {/* Legend */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem', width: '100%' }}>
        {data.map((d, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: d.color, flexShrink: 0 }} />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>{d.name}</span>
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
              {total > 0 ? `${Math.round((d.value / total) * 100)}%` : '0%'}
            </span>
          </div>
        ))}
      </div>
    </motion.div>
  )
}
