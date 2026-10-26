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
