import { render } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import App from './App'

vi.mock('./lib/api', () => ({
  getHealth: () => Promise.resolve({ api: 'ok', db: { db: 'connected' }, bedrock: 'not_configured', embedding: 'not_configured' }),
  getReasoningMode: () => Promise.resolve({ reasoning_mode: 'auto' }),
  setReasoningMode: () => Promise.resolve({ reasoning_mode: 'auto' }),
  getToolStatus: () => Promise.resolve({ tools: [] }),
  listProjects: () => Promise.resolve({ projects: [] }),
  getActivityFeed: () => Promise.resolve({ items: [] }),
  getMorningBrief: () => Promise.resolve({ brief: null }),
  getProjectAnalytics: () => Promise.resolve({ analytics: null }),
  getSystemMetrics: () => Promise.resolve({ available: false, reason: 'test', history: [] }),
  getUsageSummary: () => Promise.resolve({ total_seconds: 0, apps: [], categories: [], hourly: [], daily: [] }),
}))

describe('App Component', () => {
  it('renders without crashing', () => {
    const { container } = render(<App />)
    expect(container.firstChild).toBeInTheDocument()
  })
})
