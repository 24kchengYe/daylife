//! DayLife Desktop — Tauri 2.x 版本
//!
//! 功能：
//! - 启动 Python 后端服务
//! - 悬浮球窗口 + 快捷面板 + 完整日历窗口
//! - 系统托盘 + 全局快捷键
//! - 单实例锁

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;
use tauri::{
    AppHandle, Manager, WebviewUrl, WebviewWindowBuilder,
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
};

const PORT: u16 = 8263;
const SERVER_URL: &str = "http://127.0.0.1:8263";

/// 全局状态：Python 后端进程
struct ServerProcess(Mutex<Option<Child>>);

/// 检查服务是否已在运行
fn check_server() -> bool {
    reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
        .ok()
        .and_then(|c| c.get(&format!("{}/api/health", SERVER_URL)).send().ok())
        .map(|r| r.status().is_success())
        .unwrap_or(false)
}

/// 启动 Python 后端
fn start_server() -> Option<Child> {
    if check_server() {
        println!("[Server] Already running on port {}", PORT);
        return None;
    }

    // 尝试 daylife.exe
    let appdata = std::env::var("APPDATA").unwrap_or_default();
    let daylife_exe = format!(r"{}\Python\Python313\Scripts\daylife.exe", appdata);

    let child = Command::new(&daylife_exe)
        .args(["serve", "--port", &PORT.to_string()])
        .spawn()
        .or_else(|_| {
            // 回退到 python -m uvicorn
            let src_path = std::env::current_dir()
                .map(|p| p.join("..").join("src"))
                .unwrap_or_default();
            Command::new("python")
                .args(["-m", "uvicorn", "daylife.api.main:app",
                       "--host", "127.0.0.1", "--port", &PORT.to_string()])
                .env("PYTHONPATH", src_path)
                .spawn()
        })
        .ok();

    if child.is_some() {
        println!("[Server] Started");
    }
    child
}

/// 等待服务就绪
fn wait_for_server(retries: u32) -> bool {
    for _ in 0..retries {
        if check_server() {
            return true;
        }
        thread::sleep(Duration::from_secs(1));
    }
    false
}

// ═══ Tauri Commands (IPC) ═══

#[tauri::command]
fn get_server_url() -> String {
    SERVER_URL.to_string()
}

#[tauri::command]
fn toggle_panel(app: AppHandle) {
    if let Some(win) = app.get_webview_window("panel") {
        if win.is_visible().unwrap_or(false) {
            let _ = win.hide();
        } else {
            let _ = win.show();
            let _ = win.set_focus();
        }
    } else {
        create_panel(&app);
    }
}

#[tauri::command]
fn open_full(app: AppHandle) {
    if let Some(win) = app.get_webview_window("main") {
        let _ = win.show();
        let _ = win.set_focus();
    } else {
        create_full_window(&app);
    }
}

#[tauri::command]
fn close_panel(app: AppHandle) {
    if let Some(win) = app.get_webview_window("panel") {
        let _ = win.hide();
    }
}

// ═══ 窗口创建 ═══

fn create_float(app: &AppHandle) {
    let _ = WebviewWindowBuilder::new(
        app,
        "float",
        WebviewUrl::App("float.html".into()),
    )
    .title("DayLife Float")
    .inner_size(52.0, 52.0)
    .decorations(false)
    .transparent(true)
    .always_on_top(true)
    .resizable(false)
    .skip_taskbar(true)
    .shadow(false)
    .build();
}

fn create_panel(app: &AppHandle) {
    let _ = WebviewWindowBuilder::new(
        app,
        "panel",
        WebviewUrl::App("panel.html".into()),
    )
    .title("DayLife Panel")
    .inner_size(420.0, 600.0)
    .decorations(false)
    .transparent(true)
    .always_on_top(true)
    .resizable(true)
    .skip_taskbar(false)
    .shadow(true)
    .build();
}

fn create_full_window(app: &AppHandle) {
    let _ = WebviewWindowBuilder::new(
        app,
        "main",
        WebviewUrl::External(SERVER_URL.parse().unwrap()),
    )
    .title("DayLife - 每日记录")
    .inner_size(1400.0, 900.0)
    .build();
}

// ═══ 入口 ═══

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            // 第二次启动时激活已有窗口
            if let Some(win) = app.get_webview_window("main") {
                let _ = win.show();
                let _ = win.set_focus();
            }
        }))
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_shell::init())
        .manage(ServerProcess(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![
            get_server_url, toggle_panel, open_full, close_panel
        ])
        .setup(|app| {
            let handle = app.handle().clone();

            // 启动后端服务
            let child = start_server();
            *app.state::<ServerProcess>().0.lock().unwrap() = child;

            // 系统托盘
            let show_panel = MenuItem::with_id(app, "show_panel", "打开面板", true, None::<&str>)?;
            let show_full = MenuItem::with_id(app, "show_full", "完整日历", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "退出 DayLife", true, None::<&str>)?;

            let menu = Menu::with_items(app, &[&show_panel, &show_full, &quit])?;

            let _tray = TrayIconBuilder::new()
                .tooltip("DayLife - 每日记录")
                .menu(&menu)
                .on_menu_event(move |app, event| {
                    match event.id().as_ref() {
                        "show_panel" => { toggle_panel(app.clone()); }
                        "show_full" => { open_full(app.clone()); }
                        "quit" => {
                            // 关闭服务进程
                            if let Some(mut child) = app.state::<ServerProcess>().0.lock().unwrap().take() {
                                let _ = child.kill();
                            }
                            app.exit(0);
                        }
                        _ => {}
                    }
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event {
                        toggle_panel(tray.app_handle().clone());
                    }
                })
                .build(app)?;

            // 悬浮球
            create_float(&handle);

            // 全局快捷键
            use tauri_plugin_global_shortcut::ShortcutState;
            app.global_shortcut().on_shortcut("Alt+D", move |_app, shortcut, event| {
                if event.state == ShortcutState::Pressed {
                    toggle_panel(_app.clone());
                }
            })?;

            let handle2 = app.handle().clone();
            app.global_shortcut().on_shortcut("Alt+Shift+D", move |_app, _shortcut, event| {
                if event.state == ShortcutState::Pressed {
                    open_full(_app.clone());
                }
            })?;

            // 等服务就绪后打开完整窗口
            let handle3 = app.handle().clone();
            thread::spawn(move || {
                if wait_for_server(30) {
                    let _ = handle3.emit("server-ready", ());
                    create_full_window(&handle3);
                } else {
                    eprintln!("[Error] Server failed to start");
                }
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            // 阻止关闭面板和悬浮球窗口，改为隐藏
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let label = window.label();
                if label == "panel" || label == "float" {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running DayLife");
}
