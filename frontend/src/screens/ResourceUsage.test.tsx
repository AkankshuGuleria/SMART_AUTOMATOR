import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ResourceUsage from './ResourceUsage'

const metrics = {
  available: true,
  timestamp: 1,
  cpu: { percent: 37.5, per_core: [30, 45], cores_logical: 2, cores_physical: 1, frequency_mhz: 2400 },
  memory: { percent: 61, used_gb: 9.8, total_gb: 16, available_gb: 6.2, swap_percent: 4 },
  gpu: {
    available: true, reason: null,
    devices: [{ index: 0, name: 'RTX Test', utilization_percent: 12, temperature_c: 50, power_watts: 9.5, memory_used_mb: 512, memory_total_mb: 4096, memory_percent: 12.5 }],
  },
  disk: { mount: 'C:\\', used_gb: 200, total_gb: 500, percent: 40, read_bps: 2048, write_bps: 0 },
  network: { recv_bps: 1048576, sent_bps: 512 },
  battery: null,
  uptime_seconds: 3600,
  history: [{ t: 1, cpu: 37.5, ram: 61, gpu: 12, vram: 12.5 }],
  processes: [{ name: 'chrome.exe', cpu_percent: 8.2, memory_mb: 1500, count: 12 }],
}

const summary = {
  range: 'today', start: 0, end: 1, total_seconds: 5400, focus_percent: 66.7, app_switches: 4,
  longest_session: { app: 'VS Code', seconds: 2400, started_at: 0 },
  apps: [
    { app: 'VS Code', category: 'Development', seconds: 3600, sessions: 3, percent: 66.7, top_title: 'main.py' },
    { app: 'Chrome', category: 'Browser', seconds: 1800, sessions: 2, percent: 33.3, top_title: 'docs' },
  ],
  categories: [
    { category: 'Development', seconds: 3600, percent: 66.7 },
    { category: 'Browser', seconds: 1800, percent: 33.3 },
  ],
  hourly: Array.from({ length: 24 }, (_, h) => ({ hour: h, seconds: h === 10 ? 3600 : 0 })),
  daily: [{ day: '2026-10-25', seconds: 5400 }],
  tracking: {
    supported: true, running: true, paused: false, idle: false,
    current: { app: 'VS Code', category: 'Development', title: 'x', since: Date.now() / 1000 - 120 },
    disabled_by_env: false, error: null, db_path: 'C:\\usage.db', idle_threshold_seconds: 120,
  },
}

const setUsageTracking = vi.fn((_enabled: boolean) => Promise.resolve({ ...summary.tracking, paused: true }))

vi.mock('../lib/api', () => ({
  getSystemMetrics: () => Promise.resolve(metrics),
  getUsageSummary: () => Promise.resolve(summary),
  getUsageTimeline: () => Promise.resolve({ day: '2026-10-25', segments: [] }),
  setUsageTracking: (enabled: boolean) => setUsageTracking(enabled),
  getHealth: () => Promise.resolve({ api: 'ok', db: { db: 'connected' }, bedrock: 'not_configured', embedding: 'not_configured' }),
  getToolStatus: () => Promise.resolve({ tools: [{ name: 'git', available: true, version: 'git 2.x' }] }),
  getLiveMetrics: () => Promise.resolve(null),
}))

// recharts needs layout APIs jsdom lacks; the numbers are what we assert on.
vi.mock('../components/ui/AnimatedChart', () => ({
  ATAreaChart: () => <div data-testid="area-chart" />,
  ATBarChart: () => <div data-testid="bar-chart" />,
  ATDonutChart: ({ label }: { label?: string }) => <div data-testid="donut">{label}</div>,
}))

describe('ResourceUsage', () => {
  beforeEach(() => setUsageTracking.mockClear())

  it('shows live CPU, GPU, RAM and top processes', async () => {
    render(<ResourceUsage />)
    expect(await screen.findByText('38%')).toBeInTheDocument() // CPU 37.5 rounded
    expect(screen.getByText('61%')).toBeInTheDocument()        // RAM
    expect(screen.getAllByText('12%').length).toBeGreaterThan(0) // GPU utilisation
    expect(screen.getByText(/RTX Test/)).toBeInTheDocument()
    expect(screen.getByText('chrome.exe')).toBeInTheDocument()
    expect(screen.getByText('1.0 MB/s')).toBeInTheDocument()   // network download
  })

  it('shows app usage totals and can pause tracking', async () => {
    render(<ResourceUsage />)
    fireEvent.click(screen.getByRole('tab', { name: 'App usage' }))
    expect((await screen.findAllByText('1h 30m')).length).toBeGreaterThan(0) // active time + donut
    expect(screen.getByText('Recording')).toBeInTheDocument()
    expect(screen.getAllByText('VS Code').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: /Pause/ }))
    await waitFor(() => expect(setUsageTracking).toHaveBeenCalledWith(false))
  })
})
