use tauri_plugin_global_shortcut::GlobalShortcutExt;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .plugin(tauri_plugin_global_shortcut::Builder::new().build())
    .plugin(
      tauri_plugin_log::Builder::default()
        .level(log::LevelFilter::Info)
        .build(),
    )
    .setup(|app| {
      use tauri::Manager;

      let companion_window = match app.get_webview_window("companion") {
        Some(w) => w,
        None => {
            eprintln!("Companion window missing: the Tauri config must declare a window with label 'companion'");
            return Ok(());
        }
      };
      let _main_window = match app.get_webview_window("main") {
        Some(w) => w,
        None => {
            eprintln!("Main window missing: the Tauri config must declare a window with label 'main'");
            return Ok(());
        }
      };

      let shortcut = app
        .global_shortcut()
        .on_shortcut("Alt+Space", move |_app, _shortcut, _event| {
          let _ = companion_window.is_visible().map(|visible| {
            if visible {
              let _ = companion_window.hide();
            } else {
              let _ = companion_window.show();
              let _ = companion_window.set_focus();
            }
          });
        });

      if shortcut.is_err() {
        eprintln!("Failed to register global shortcut: {:?}", shortcut);
      }

      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
