import { render } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import App from './App'

vi.mock('./lib/api', () => ({
  getHealth: () => Promise.resolve({ api: 'ok', db: { db: 'connected' }, bedrock: 'not_configured', embedding: 'not_configured' }),
  getReasoningMode: () => Promise.resolve({ reasoning_mode: 'auto' }),
  setReasoningMode: () => Promise.resolve({ reasoning_mode: 'auto' }),
  getToolStatus: () => Promise.resolve({ tools: [] }),
}))

describe('App Component', () => {
  it('renders without crashing', () => {
    const { container } = render(<App />)
    expect(container.firstChild).toBeInTheDocument()
  })
})
