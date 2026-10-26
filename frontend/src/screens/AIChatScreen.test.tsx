import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import AIChatScreen from './AIChatScreen'

// A reply that echoes attacker-controlled text (a commit message, OCR'd screen text…).
const hostile = 'Last commit: **<img src=x onerror="window.__pwned=1">** in `<script>alert(1)</script>`'

vi.mock('../lib/api', () => ({
  sendChatMessage: () => Promise.resolve({ intent: 'general_assistant', reply: hostile, actions: [] }),
  approveAction: () => Promise.resolve({ executed: false }),
  getChatHistory: () => Promise.resolve({ messages: [] }),
}))

describe('AIChatScreen', () => {
  it('shows replies as text, never as HTML', async () => {
    const { container } = render(<AIChatScreen projectId="p1" initialMessage="what changed?" />)
    await waitFor(() => expect(screen.getByText(/Last commit:/)).toBeTruthy())
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('script')).toBeNull()
    expect((window as unknown as { __pwned?: number }).__pwned).toBeUndefined()
    // formatting still works, with the markup shown literally
    expect(container.querySelector('b')?.textContent).toBe('<img src=x onerror="window.__pwned=1">')
    expect(container.querySelector('code')?.textContent).toBe('<script>alert(1)</script>')
  })
})
