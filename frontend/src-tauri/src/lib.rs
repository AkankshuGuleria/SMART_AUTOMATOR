//! AUTOMATA desktop shell.
//!
//! - Lives in the system tray; closing the window hides it (the agent keeps running).
//! - Single instance: launching again focuses the existing window.
//! - Optional start at sign-in (autostart plugin) — starts hidden with `--hidden`.
//! - Supervises the Python backend: starts it if nothing answers on 127.0.0.1:8000
//!   and restarts it if it dies (at most a few times per minute).
//! - A global shortcut (Alt+Space by default, changeable in Settings and saved in
//!   the app config folder) toggles the AI work bar: a frameless panel at the top
//!   centre of the screen that hides on Esc or when it loses focus.

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Manager, PhysicalPosition, WebviewWindow, WindowEvent};
use tauri_plugin_autostart::MacosLauncher;
use serde::Serialize;
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};

/// Default work bar shortcut. Changeable in Settings (Ctrl+Alt+A is avoided: Kilo
/// Code uses it for "toggle auto-approve").
const DEFAULT_WORKBAR_SHORTCUT: &str = "Alt+Space";

/// Never register these globally: Kilo Code and editors need them inside apps.
const RESERVED_SHORTCUTS: [&str; 6] = [
    "Ctrl+Shift+A", "Ctrl+Alt+A", "Ctrl+Shift+M", "Ctrl+Shift+Space", "Ctrl+Space", "Ctrl+Shift+P",
];

fn is_reserved(shortcut: &str) -> bool {
    RESERVED_SHORTCUTS.iter().any(|r| r.eq_ignore_ascii_case(shortcut.trim()))
}

/// The work bar shortcut in use and whether Windows accepted it.
struct Workbar(Mutex<WorkbarStatus>);

#[derive(Clone, Serialize)]
struct WorkbarStatus {
    shortcut: String,
    registered: bool,
    error: Option<String>,
}

fn workbar_config_path(app: &AppHandle) -> Option<PathBuf> {
    app.path().app_config_dir().ok().map(|d| d.join("workbar.json"))
}

fn load_workbar_shortcut(app: &AppHandle) -> String {
    workbar_config_path(app)
        .and_then(|p| std::fs::read_to_string(p).ok())
        .and_then(|t| serde_json::from_str::<serde_json::Value>(&t).ok())
        .and_then(|v| v.get("shortcut").and_then(|s| s.as_str()).map(str::to_string))
        .filter(|s| !s.trim().is_empty() && !is_reserved(s))
        .unwrap_or_else(|| DEFAULT_WORKBAR_SHORTCUT.to_string())
}

fn save_workbar_shortcut(app: &AppHandle, shortcut: &str) {
    if let Some(path) = workbar_config_path(app) {
        if let Some(dir) = path.parent() {
            let _ = std::fs::create_dir_all(dir);
        }
        let _ = std::fs::write(path, serde_json::json!({ "shortcut": shortcut }).to_string());
    }
}

/// Register *shortcut* to toggle the bar (on key-down only: the handler also
/// fires on key-up, which used to close the bar in the same keypress).
fn register_workbar_shortcut(app: &AppHandle, shortcut: &str) -> Result<(), String> {
    let parsed: Shortcut = shortcut.parse().map_err(|e| format!("'{shortcut}' is not a valid shortcut: {e}"))?;
    app.global_shortcut()
        .on_shortcut(parsed, |app, _shortcut, event| {
            if event.state() == ShortcutState::Pressed {
                toggle_workbar(app);
            }
        })
        .map_err(|e| format!("{shortcut} is already used by another app or by Windows ({e})"))
}

#[tauri::command]
fn get_workbar_shortcut(state: tauri::State<'_, Workbar>) -> WorkbarStatus {
    state.0.lock().unwrap().clone()
}

/// Switch to a new shortcut. On failure the previous one stays active.
#[tauri::command]
fn set_workbar_shortcut(app: AppHandle, state: tauri::State<'_, Workbar>, shortcut: String) -> Result<WorkbarStatus, String> {
    let shortcut = shortcut.trim().to_string();
    if shortcut.is_empty() {
        return Err("Choose a key combination.".into());
    }
    if is_reserved(&shortcut) {
        return Err(format!("{shortcut} is used by Kilo Code or your editor; pick another combination."));
    }
    let mut current = state.0.lock().unwrap();
    if current.registered && current.shortcut.eq_ignore_ascii_case(&shortcut) {
        return Ok(current.clone());
    }
    let old = current.shortcut.clone();
    if current.registered {
        if let Ok(parsed) = old.parse::<Shortcut>() {
            let _ = app.global_shortcut().unregister(parsed);
        }
    }
    match register_workbar_shortcut(&app, &shortcut) {
        Ok(()) => {
            save_workbar_shortcut(&app, &shortcut);
            *current = WorkbarStatus { shortcut, registered: true, error: None };
            Ok(current.clone())
        }
        Err(err) => {
            let restored = current.registered && register_workbar_shortcut(&app, &old).is_ok();
            current.registered = restored;
            Err(err)
        }
    }
}

#[tauri::command]
fn toggle_workbar_cmd(app: AppHandle) {
    toggle_workbar(&app);
}

const BACKEND_ADDR: &str = "127.0.0.1:8000";

/// Backend process this app started (None if it was already running).
struct Backend(Mutex<Option<Child>>);

fn backend_alive() -> bool {
    let addr: SocketAddr = BACKEND_ADDR.parse().expect("valid address");
    TcpStream::connect_timeout(&addr, Duration::from_millis(600)).is_ok()
}

/// Find `backend/main.py`: AUTOMATA_BACKEND_DIR, then walk up from the exe and cwd.
fn find_backend_dir() -> Option<PathBuf> {
    if let Ok(dir) = std::env::var("AUTOMATA_BACKEND_DIR") {
        let p = PathBuf::from(dir);
        if p.join("main.py").exists() {
            return Some(p);
        }
    }
    let mut starts: Vec<PathBuf> = Vec::new();
    if let Ok(exe) = std::env::current_exe() {
        starts.push(exe);
    }
    if let Ok(cwd) = std::env::current_dir() {
        starts.push(cwd);
    }
    for start in starts {
        let mut cur: Option<&Path> = Some(start.as_path());
        while let Some(dir) = cur {
            let candidate = dir.join("backend");
            if candidate.join("main.py").exists() {
                return Some(candidate);
            }
            cur = dir.parent();
        }
    }
    None
}

fn spawn_backend() -> Option<Child> {
    let dir = find_backend_dir()?;
    let pythonw = dir.join(".venv").join("Scripts").join("pythonw.exe");
    let python = if pythonw.exists() { pythonw } else { PathBuf::from("pythonw") };
    let mut cmd = Command::new(python);
    cmd.arg("main.py").current_dir(&dir);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    match cmd.spawn() {
        Ok(child) => {
            log::info!("started backend from {}", dir.display());
            Some(child)
        }
        Err(err) => {
            log::error!("could not start backend: {err}");
            None
        }
    }
}

/// Keep the backend up. Restarts are rate-limited so a crash loop cannot spin.
fn supervise_backend(app: AppHandle) {
    thread::spawn(move || {
        let mut restarts: Vec<Instant> = Vec::new();
        loop {
            if !backend_alive() {
                restarts.retain(|t| t.elapsed() < Duration::from_secs(60));
                if restarts.len() < 3 {
                    let state = app.state::<Backend>();
                    let mut guard = state.0.lock().unwrap();
                    let exited = match guard.as_mut() {
                        Some(child) => child.try_wait().map(|s| s.is_some()).unwrap_or(true),
                        None => true,
                    };
                    if exited {
                        *guard = spawn_backend();
                        restarts.push(Instant::now());
                    }
                }
            }
            thread::sleep(Duration::from_secs(10));
        }
    });
}

/// Minimal local HTTP POST (avoids pulling in an HTTP client crate).
fn post_json(path: &str, body: &str) -> bool {
    let addr: SocketAddr = BACKEND_ADDR.parse().expect("valid address");
    let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_secs(2)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(3)));
    let req = format!(
        "POST {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    if stream.write_all(req.as_bytes()).is_err() {
        return false;
    }
    let mut buf = [0u8; 64];
    matches!(stream.read(&mut buf), Ok(n) if n > 12 && &buf[9..12] == b"200")
}

fn show_main(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.unminimize();
        let _ = w.show();
        let _ = w.set_focus();
    }
}

/// Put the work bar at the top centre of the monitor the cursor is on.
fn place_workbar(bar: &WebviewWindow) {
    let monitor = bar
        .cursor_position()
        .ok()
        .and_then(|p| bar.monitor_from_point(p.x, p.y).ok().flatten())
        .or_else(|| bar.current_monitor().ok().flatten());
    if let (Some(m), Ok(size)) = (monitor, bar.outer_size()) {
        let area = m.work_area();
        let x = area.position.x + (area.size.width as i32 - size.width as i32) / 2;
        let y = area.position.y + (area.size.height as f64 * 0.08) as i32;
        let _ = bar.set_position(PhysicalPosition::new(x, y));
    }
}

/// When the bar was last shown: focus can bounce away for a moment right after a
/// global hotkey (the OS foreground lock, a stray Alt key), which must not hide it.
static WORKBAR_SHOWN_AT: Mutex<Option<Instant>> = Mutex::new(None);
const WORKBAR_GRACE: Duration = Duration::from_millis(800);

fn toggle_workbar(app: &AppHandle) {
    if let Some(bar) = app.get_webview_window("companion") {
        if bar.is_visible().unwrap_or(false) {
            let _ = bar.hide();
        } else {
            place_workbar(&bar);
            *WORKBAR_SHOWN_AT.lock().unwrap() = Some(Instant::now());
            let _ = bar.show();
            let _ = bar.set_focus();
            // Focusing the window does not move keyboard focus into WebView2 on
            // Windows: without this, typing right after the shortcut goes nowhere.
            #[cfg(windows)]
            let _ = bar.with_webview(|webview| unsafe {
                use webview2_com::Microsoft::Web::WebView2::Win32::COREWEBVIEW2_MOVE_FOCUS_REASON_PROGRAMMATIC;
                let _ = webview.controller().MoveFocus(COREWEBVIEW2_MOVE_FOCUS_REASON_PROGRAMMATIC);
            });
        }
    }
}

fn build_tray(app: &AppHandle) -> tauri::Result<()> {
    let open = MenuItem::with_id(app, "open", "Open AUTOMATA", true, None::<&str>)?;
    let quick = MenuItem::with_id(app, "quick", "Open AI work bar", true, None::<&str>)?;
    let snapshot = MenuItem::with_id(app, "snapshot", "Save where I left off", true, None::<&str>)?;
    let pause = MenuItem::with_id(app, "pause", "Pause app-usage tracking", true, None::<&str>)?;
    let resume = MenuItem::with_id(app, "resume", "Resume app-usage tracking", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit window (agent keeps running)", true, None::<&str>)?;
    let stop_all = MenuItem::with_id(app, "stop_all", "Quit and stop agent", true, None::<&str>)?;
    let sep = PredefinedMenuItem::separator(app)?;
    let sep2 = PredefinedMenuItem::separator(app)?;
    let menu = Menu::with_items(
        app,
        &[&open, &quick, &snapshot, &sep, &pause, &resume, &sep2, &quit, &stop_all],
    )?;

    TrayIconBuilder::with_id("main-tray")
        .icon(app.default_window_icon().cloned().expect("bundle icon"))
        .tooltip("AUTOMATA — running in the background")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "open" => show_main(app),
            "quick" => toggle_workbar(app),
            "snapshot" => {
                let _ = post_json("/workspace/snapshot-active", "{}");
            }
            "pause" => {
                let _ = post_json("/usage/tracking", r#"{"enabled": false}"#);
            }
            "resume" => {
                let _ = post_json("/usage/tracking", r#"{"enabled": true}"#);
            }
            "quit" => app.exit(0),
            "stop_all" => {
                let _ = post_json("/workspace/snapshot-active", "{}");
                if let Some(mut child) = app.state::<Backend>().0.lock().unwrap().take() {
                    let _ = child.kill();
                }
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = event {
                let app = tray.app_handle();
                if let Some(w) = app.get_webview_window("main") {
                    if w.is_visible().unwrap_or(false) {
                        let _ = w.hide();
                    } else {
                        show_main(app);
                    }
                }
            }
        })
        .build(app)?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        // Must be registered first: a second launch just focuses this one.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| show_main(app)))
        .plugin(tauri_plugin_autostart::init(
            MacosLauncher::LaunchAgent,
            Some(vec!["--hidden"]),
        ))
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(
            tauri_plugin_log::Builder::default()
                .level(log::LevelFilter::Info)
                .build(),
        )
        .manage(Backend(Mutex::new(None)))
        .manage(Workbar(Mutex::new(WorkbarStatus {
            shortcut: DEFAULT_WORKBAR_SHORTCUT.to_string(),
            registered: false,
            error: None,
        })))
        .invoke_handler(tauri::generate_handler![get_workbar_shortcut, set_workbar_shortcut, toggle_workbar_cmd])
        .setup(|app| {
            let handle = app.handle().clone();
            build_tray(&handle)?;
            supervise_backend(handle.clone());

            if std::env::args().any(|a| a == "--hidden") {
                if let Some(w) = app.get_webview_window("main") {
                    let _ = w.hide();
                }
            }

            let shortcut = load_workbar_shortcut(&handle);
            let result = register_workbar_shortcut(&handle, &shortcut);
            if let Err(err) = &result {
                log::warn!("work bar shortcut not registered: {err}");
            }
            *app.state::<Workbar>().0.lock().unwrap() = WorkbarStatus {
                shortcut,
                registered: result.is_ok(),
                error: result.err(),
            };
            Ok(())
        })
        .on_window_event(|window, event| match event {
            // Closing hides to the tray; use the tray menu to quit.
            WindowEvent::CloseRequested { api, .. } => {
                api.prevent_close();
                let _ = window.hide();
            }
            // Like a game bar: click anywhere else and it gets out of the way. Moving
            // keyboard focus into the web content also reports "lost focus" for the
            // window itself, so only hide if it really is no longer the active window.
            WindowEvent::Focused(false) if window.label() == "companion" => {
                let bar = window.clone();
                thread::spawn(move || {
                    thread::sleep(Duration::from_millis(150));
                    if bar.is_focused().unwrap_or(false) {
                        return;
                    }
                    let just_opened = WORKBAR_SHOWN_AT.lock().unwrap()
                        .map(|t| t.elapsed() < WORKBAR_GRACE)
                        .unwrap_or(false);
                    if just_opened {
                        let _ = bar.set_focus(); // take focus back instead of vanishing
                    } else {
                        let _ = bar.hide();
                    }
                });
            }
            _ => {}
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
