/**
 * lib/permissions.ts — ask the user before AUTOMATA controls the PC.
 *
 * The backend answers a gated request with `needs_permission` (a single-use
 * request id). `withPermission` shows the prompt (rendered by <PermissionHost/>),
 * and on "Allow once" resends the same call with that id; "Always allow" also
 * saves the choice for that category. The server stays the judge: an id only
 * works once, for that exact action, for a few minutes.
 */
import { apiFetch } from './api'

export interface PermissionRequest {
  id: string
  category: string
  label: string
  help: string
  action: string
}
export type PermissionDecision = 'once' | 'always' | 'deny'
export interface PermissionPolicy { category: string; mode: 'ask' | 'allow'; label: string; help: string }

type Listener = (req: PermissionRequest, resolve: (d: PermissionDecision) => void) => void
let listener: Listener | null = null

/** <PermissionHost/> registers itself here. */
export function setPermissionListener(fn: Listener | null): void {
  listener = fn
}

export function askPermission(req: PermissionRequest): Promise<PermissionDecision> {
  if (!listener) return Promise.resolve('deny') // no UI to ask with: never act silently
  return new Promise(resolve => listener!(req, resolve))
}

export const getPermissions = () => apiFetch<{ permissions: PermissionPolicy[] }>('/permissions')
export const setPermission = (category: string, mode: 'ask' | 'allow') =>
  apiFetch<{ category: string; mode: string }>('/permissions', { method: 'POST', body: JSON.stringify({ category, mode }) })

/**
 * Run *call*; if the backend asks for permission, ask the user and retry once
 * with the approval. Returns the final result, or the original one with
 * `denied: true` when the user says no.
 */
export async function withPermission<T extends { needs_permission?: PermissionRequest | null }>(
  call: (permissionId?: string) => Promise<T>,
): Promise<T & { denied?: boolean }> {
  const first = await call()
  const req = first?.needs_permission
  if (!req) return first
  const decision = await askPermission(req)
  if (decision === 'deny') return { ...first, denied: true }
  if (decision === 'always') {
    try { await setPermission(req.category, 'allow') } catch { /* still allow this once */ }
  }
  return call(req.id)
}
