import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TasksScreen from './TasksScreen'
import InboxScreen from './InboxScreen'

const task = {
  id: 't1', project_id: 'p1', title: 'Create a landing page', request: 'using antigravity create a landing page',
  agent: 'antigravity', status: 'waiting_approval', current_step: 2, created_at: 1, updated_at: Date.now() / 1000,
  summary: null, steps_total: 7, steps_done: 2,
  steps: [
    { id: 1, idx: 0, kind: 'context', title: 'Gather project context', policy: 'auto', status: 'done', detail: '3 related memories', output: {}, started_at: 1, finished_at: 2 },
    { id: 2, idx: 1, kind: 'prompt', title: 'Write the prompt for Antigravity', policy: 'auto', status: 'done', detail: '900 characters', output: { prompt: '# Task\nCreate a landing page' }, started_at: 1, finished_at: 2 },
    { id: 3, idx: 2, kind: 'handoff', title: 'Hand the task to Antigravity', policy: 'approval', status: 'waiting_approval', detail: '', output: null, started_at: null, finished_at: null },
  ],
  needs: [{ id: 'n1', var: 'STRIPE_SECRET_KEY', status: 'open' }],
}

const approveTask = vi.fn((_id: string) => Promise.resolve({ success: true }))
const resolveNeed = vi.fn((..._args: unknown[]) => Promise.resolve({ success: true, saved_to: ['Windows Credential Manager'], warnings: [] }))

vi.mock('../lib/api', () => ({
  listTasks: () => Promise.resolve({ tasks: [task] }),
  getTask: () => Promise.resolve({ task }),
  createTask: () => Promise.resolve({ success: true, task }),
  approveTask: (id: string) => approveTask(id),
  cancelTask: () => Promise.resolve({ success: true }),
  listNeeds: () => Promise.resolve({ needs: [{
    id: 'n1', task_id: 't1', project_id: 'p1', var: 'STRIPE_SECRET_KEY', kind: 'api_key', provider: 'Stripe',
    title: 'Stripe needed', steps: ['Sign in at dashboard.stripe.com', 'Copy the secret key'],
    docs_url: 'https://dashboard.stripe.com/apikeys', target_file: 'C:/shop/.env', status: 'open', created_at: 1,
  }] }),
  resolveNeed: (...args: unknown[]) => resolveNeed(...args),
}))

describe('TasksScreen', () => {
  beforeEach(() => approveTask.mockClear())

  it('shows the waiting step and approves it', async () => {
    render(<TasksScreen projectId="p1" />)
    expect((await screen.findAllByText('Create a landing page')).length).toBeGreaterThan(0)
    const approve = await screen.findByRole('button', { name: /Approve: Hand the task to Antigravity/ })
    fireEvent.click(approve)
    await waitFor(() => expect(approveTask).toHaveBeenCalledWith('t1'))
    expect(screen.getByText('STRIPE_SECRET_KEY')).toBeInTheDocument()
  })
})

describe('InboxScreen', () => {
  it('saves a key with instructions shown and never echoes it', async () => {
    render(<InboxScreen projectId="p1" />)
    expect(await screen.findByText('STRIPE_SECRET_KEY')).toBeInTheDocument()
    expect(screen.getByText('Sign in at dashboard.stripe.com')).toBeInTheDocument()
    const input = screen.getByPlaceholderText('Paste STRIPE_SECRET_KEY') as HTMLInputElement
    expect(input.type).toBe('password')
    fireEvent.change(input, { target: { value: 'sk_test_abc' } })
    fireEvent.click(screen.getByRole('button', { name: /Save/ }))
    await waitFor(() => expect(resolveNeed).toHaveBeenCalledWith('n1', 'both', 'sk_test_abc'))
    expect(await screen.findByText(/Saved to Windows Credential Manager/)).toBeInTheDocument()
    expect(screen.queryByText('sk_test_abc')).not.toBeInTheDocument()
  })
})
