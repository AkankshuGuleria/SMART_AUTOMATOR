import { render, screen, within } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import App from './App'

vi.mock('./lib/api', () => ({
  getHealth: () => Promise.resolve({ api: 'ok', db: { db: 'connected' }, bedrock: 'not_configured', embedding: 'not_configured' }),
  getReasoningMode: () => Promise.resolve({ reasoning_mode: 'auto' }),
  setReasoningMode: () => Promise.resolve({ reasoning_mode: 'auto' }),
  getToolStatus: () => Promise.resolve({ tools: [] }),
}))

describe('App Component', () => {
  it('renders the AUTOMATA header', () => {
    render(<App />)
    expect(screen.getByText('AUTOMATA')).toBeInTheDocument()
  })

  it('renders navigation tabs', () => {
    render(<App />)
    const nav = screen.getByRole('navigation', { name: /primary/i })
    expect(within(nav).getByRole('button', { name: /chat/i })).toBeInTheDocument()
    expect(within(nav).getByRole('button', { name: /projects/i })).toBeInTheDocument()
    expect(within(nav).getByRole('button', { name: /activity/i })).toBeInTheDocument()
    expect(within(nav).getByRole('button', { name: /brief/i })).toBeInTheDocument()
  })
})
