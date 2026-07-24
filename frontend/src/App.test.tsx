import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import App from './App'

describe('App Component', () => {
  it('renders the AUTOMATA header', () => {
    render(<App />)
    expect(screen.getByText('AUTOMATA')).toBeInTheDocument()
  })

  it('renders navigation tabs', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: /morning brief/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /restore workspace/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /memory query/i })).toBeInTheDocument()
  })
})
