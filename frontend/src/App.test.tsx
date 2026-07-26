import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import App from './App'

vi.mock('./lib/api', () => ({
  getHealth: () => Promise.resolve({ api: 'ok', db: { db: 'connected' }, bedrock: 'not_configured', embedding: 'not_configured' }),
  getToolStatus: () => Promise.resolve({ tools: [] }),
}))

describe('App Component', () => {
  it('renders the AUTOMATA header', () => {
    render(<App />)
    expect(screen.getByText('AUTOMATA')).toBeInTheDocument()
  })

  it('renders navigation tabs', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: /chat/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /projects/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /activity/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /brief/i })).toBeInTheDocument()
  })
})
