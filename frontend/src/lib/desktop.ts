/**
 * lib/desktop.ts — features that only exist inside the Tauri desktop app.
 *
 * Every function is safe to call in a plain browser: it detects Tauri and
 * returns null/false instead of throwing. Plugins load lazily so the web
 * bundle does not pay for them.
 */

export function isTauri(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
}

/** App start-at-sign-in (registry Run key managed by tauri-plugin-autostart). */
export async function appAutostartEnabled(): Promise<boolean | null> {
  if (!isTauri()) return null
  try {
    const { isEnabled } = await import('@tauri-apps/plugin-autostart')
    return await isEnabled()
  } catch {
    return null
  }
}

export async function setAppAutostart(enabled: boolean): Promise<boolean> {
  if (!isTauri()) return false
  const plugin = await import('@tauri-apps/plugin-autostart')
  if (enabled) await plugin.enable()
  else await plugin.disable()
  return await plugin.isEnabled()
}

let notifyAllowed: boolean | null = null

/** Native Windows notification (desktop app only). */
export async function notify(title: string, body: string): Promise<void> {
  if (!isTauri()) return
  try {
    const n = await import('@tauri-apps/plugin-notification')
    if (notifyAllowed === null) {
      notifyAllowed = (await n.isPermissionGranted()) || (await n.requestPermission()) === 'granted'
    }
    if (notifyAllowed) n.sendNotification({ title, body })
  } catch {
    /* notifications are best-effort */
  }
}

/** Show and focus the main window (used from the companion window). */
export async function showMainWindow(): Promise<void> {
  if (!isTauri()) return
  try {
    const { Window } = await import('@tauri-apps/api/window')
    const main = await Window.getByLabel('main')
    await main?.show()
    await main?.setFocus()
  } catch {
    /* ignore */
  }
}

/** Hide the window this code runs in (the work bar hides itself on Esc). */
export async function hideCurrentWindow(): Promise<void> {
  if (!isTauri()) return
  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window')
    await getCurrentWindow().hide()
  } catch {
    /* ignore */
  }
}

/** Open the main window on a given screen (from the work bar). */
export async function openMainScreen(screen: string): Promise<void> {
  if (!isTauri()) return
  try {
    const { emitTo } = await import('@tauri-apps/api/event')
    await emitTo('main', 'open-screen', screen)
  } catch {
    /* ignore */
  }
  await showMainWindow()
}

/** Main window: react to "open this screen" requests from the work bar. */
export async function onOpenScreen(handler: (screen: string) => void): Promise<() => void> {
  if (!isTauri()) return () => {}
  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window')
    return await getCurrentWindow().listen<string>('open-screen', e => handler(e.payload))
  } catch {
    return () => {}
  }
}

export interface WorkbarShortcut {
  shortcut: string
  registered: boolean
  error?: string | null
}

/** Current work bar shortcut (desktop app only). */
export async function getWorkbarShortcut(): Promise<WorkbarShortcut | null> {
  if (!isTauri()) return null
  try {
    const { invoke } = await import('@tauri-apps/api/core')
    return await invoke<WorkbarShortcut>('get_workbar_shortcut')
  } catch {
    return null
  }
}

/** Change the work bar shortcut; throws with a readable message if Windows refuses it. */
export async function setWorkbarShortcut(shortcut: string): Promise<WorkbarShortcut> {
  const { invoke } = await import('@tauri-apps/api/core')
  try {
    return await invoke<WorkbarShortcut>('set_workbar_shortcut', { shortcut })
  } catch (e) {
    throw new Error(typeof e === 'string' ? e : e instanceof Error ? e.message : 'Could not set the shortcut')
  }
}

/** Show or hide the work bar. */
export async function toggleWorkbar(): Promise<void> {
  if (!isTauri()) return
  const { invoke } = await import('@tauri-apps/api/core')
  await invoke('toggle_workbar_cmd')
}

/** Turn a keydown event into a shortcut string ("Ctrl+Shift+K"), or null while only modifiers are held. */
export function shortcutFromEvent(e: { code: string; key?: string; ctrlKey: boolean; altKey: boolean; shiftKey: boolean; metaKey: boolean }): string | null {
  const code = e.code ?? ''
  const k = e.key ?? ''
  if (/^(Control|Shift|Alt|Meta)(Left|Right)?$/.test(code) || ['Control', 'Shift', 'Alt', 'Meta'].includes(k)) return null
  let key: string | null = null
  if (/^Key[A-Z]$/.test(code)) key = code.slice(3)
  // Some tools send keys without a scan code (code is empty): use the key value.
  else if (!code && /^[a-z0-9]$/i.test(k)) key = k.toUpperCase()
  else if (!code && k === ' ') key = 'Space'
  else if (/^Digit\d$/.test(code)) key = code.slice(5)
  else if (/^F\d{1,2}$/.test(code)) key = code
  else if (['Space', 'Enter', 'Tab', 'Backquote', 'Minus', 'Equal', 'BracketLeft', 'BracketRight', 'Backslash',
    'Semicolon', 'Quote', 'Comma', 'Period', 'Slash', 'Home', 'End', 'PageUp', 'PageDown', 'Insert',
    'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(code)) key = code
  if (!key) return null
  const mods = [e.ctrlKey && 'Ctrl', e.altKey && 'Alt', e.shiftKey && 'Shift', e.metaKey && 'Super'].filter(Boolean)
  if (!mods.length && !/^F\d{1,2}$/.test(key)) return null // plain letters would block typing everywhere
  return [...mods, key].join('+')
}

/** Shortcuts other tools rely on: a global hotkey would steal them everywhere. */
export const RESERVED_SHORTCUTS: Record<string, string> = {
  'Ctrl+Shift+A': 'Kilo Code uses it to focus its chat',
  'Ctrl+Alt+A': 'Kilo Code uses it to toggle auto-approve',
  'Ctrl+Shift+M': 'Kilo Code / VS Code use it',
  'Ctrl+Shift+Space': 'editors use it for parameter hints',
  'Ctrl+Space': 'editors use it for autocomplete',
  'Ctrl+Shift+P': 'command palette in editors',
  'Ctrl+C': 'copy', 'Ctrl+V': 'paste', 'Ctrl+X': 'cut', 'Ctrl+Z': 'undo', 'Ctrl+S': 'save', 'Ctrl+A': 'select all',
  'Ctrl+L': 'Antigravity agent panel / browser address bar',
  'Alt+Tab': 'Windows app switching', 'Alt+F4': 'closes windows',
}
