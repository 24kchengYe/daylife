const { app, BrowserWindow, Tray, Menu, globalShortcut, ipcMain, screen, nativeImage } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

// ═══ App identity ═══
app.setName('DayLife');
app.setAppUserModelId('com.DayLife.dev');

// ═══ 单实例锁：防止重复启动 ═══
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
    // 已有实例在运行，直接退出
    app.quit();
}

let floatWin = null;
let panelWin = null;
let fullWin = null;
let tray = null;
let serverProcess = null;
const PORT = 8263;
const SERVER_URL = `http://127.0.0.1:${PORT}`;

// ═══ 启动后端服务 ═══
function startServer() {
    // 检查服务是否已在运行
    checkServer().then(running => {
        if (running) {
            console.log('[Server] Already running on port', PORT);
            return;
        }
        const daylifeExe = path.join(
            process.env.APPDATA, 'Python', 'Python313', 'Scripts', 'daylife.exe'
        );
        serverProcess = spawn(daylifeExe, ['serve', '--port', String(PORT)], {
            stdio: 'ignore', detached: false,
        });
        serverProcess.on('error', () => {
            serverProcess = spawn('python', ['-m', 'uvicorn', 'daylife.api.main:app',
                '--host', '127.0.0.1', '--port', String(PORT)], {
                stdio: 'ignore',
                env: { ...process.env, PYTHONPATH: path.join(__dirname, '..', 'src') },
            });
        });
        console.log('[Server] Started');
    });
}

function checkServer() {
    return new Promise(resolve => {
        const req = http.get(`${SERVER_URL}/api/health`, res => {
            resolve(res.statusCode === 200);
        });
        req.on('error', () => resolve(false));
        req.setTimeout(1000, () => { req.destroy(); resolve(false); });
    });
}

// ═══ 图标 ═══
function getIconPath() {
    return path.join(__dirname, 'icon.ico');
}
function getIcon() {
    return nativeImage.createFromPath(path.join(__dirname, 'icon.png'));
}

// ═══ 悬浮按钮（可拖动） ═══
function createFloatButton() {
    const { width, height } = screen.getPrimaryDisplay().workAreaSize;

    floatWin = new BrowserWindow({
        width: 52, height: 52,
        x: width - 80, y: height - 200,
        frame: false, transparent: true,
        alwaysOnTop: true, resizable: false,
        skipTaskbar: true, hasShadow: false,
        icon: getIconPath(),
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
        },
    });
    floatWin.loadFile(path.join(__dirname, 'float.html'));
    floatWin.setVisibleOnAllWorkspaces(true);
    floatWin.on('close', e => { e.preventDefault(); floatWin.hide(); });
}

// ═══ 快捷面板（小窗口） ═══
function createPanel() {
    if (panelWin && !panelWin.isDestroyed()) {
        panelWin.show(); panelWin.focus(); return;
    }
    const { width, height } = screen.getPrimaryDisplay().workAreaSize;
    panelWin = new BrowserWindow({
        width: 420, height: 600,
        x: width - 440, y: height - 640,
        frame: false, transparent: true,
        alwaysOnTop: true, resizable: true,
        skipTaskbar: false, hasShadow: true,
        icon: getIconPath(),
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
        },
    });
    panelWin.loadFile(path.join(__dirname, 'panel.html'));
    panelWin.on('close', e => { e.preventDefault(); panelWin.hide(); });
}

function togglePanel() {
    if (panelWin && !panelWin.isDestroyed() && panelWin.isVisible()) {
        panelWin.hide();
    } else {
        createPanel();
    }
}

// ═══ 完整日历窗口（Electron 内嵌 Web） ═══
function openFullWindow() {
    if (fullWin && !fullWin.isDestroyed()) {
        fullWin.show(); fullWin.focus(); return;
    }
    fullWin = new BrowserWindow({
        width: 1400, height: 900,
        icon: getIconPath(),
        title: 'DayLife - 每日记录',
        webPreferences: {
            contextIsolation: false,
            nodeIntegration: false,
            zoomFactor: 1.25,
        },
    });
    fullWin.loadURL(SERVER_URL);
    fullWin.setMenuBarVisibility(false);
    enableZoom(fullWin);
    fullWin.on('closed', () => { fullWin = null; });
}

// ═══ 系统托盘 ═══
function createTray() {
    tray = new Tray(getIcon());
    tray.setToolTip('DayLife - 每日记录');
    tray.setContextMenu(Menu.buildFromTemplate([
        { label: '打开面板', click: togglePanel },
        { label: '完整日历', click: openFullWindow },
        { type: 'separator' },
        { label: '显示悬浮球', click: () => floatWin?.show() },
        { label: '隐藏悬浮球', click: () => floatWin?.hide() },
        { type: 'separator' },
        { label: '退出 DayLife', click: () => {
            if (serverProcess) serverProcess.kill();
            app.exit(0);
        }},
    ]));
    tray.on('click', togglePanel);
    tray.on('double-click', openFullWindow);
}

// ═══ Zoom support ═══
function enableZoom(win) {
    // Ctrl+=/- keyboard zoom
    win.webContents.on('before-input-event', (event, input) => {
        if (input.control && input.type === 'keyDown') {
            const z = win.webContents.getZoomFactor();
            if (input.key === '=' || input.key === '+') {
                win.webContents.setZoomFactor(Math.min(z + 0.1, 3));
            } else if (input.key === '-') {
                win.webContents.setZoomFactor(Math.max(z - 0.1, 0.5));
            } else if (input.key === '0') {
                win.webContents.setZoomFactor(1.25);
            }
        }
    });
    // Ctrl+scroll zoom
    win.webContents.on('zoom-changed', (event, direction) => {
        const z = win.webContents.getZoomFactor();
        if (direction === 'in') win.webContents.setZoomFactor(Math.min(z + 0.1, 3));
        else win.webContents.setZoomFactor(Math.max(z - 0.1, 0.5));
    });
}

// ═══ IPC ═══
ipcMain.on('toggle-panel', togglePanel);
ipcMain.on('open-browser', openFullWindow);
ipcMain.on('close-panel', () => panelWin?.hide());
ipcMain.on('move-float', (_, dx, dy) => {
    if (floatWin && !floatWin.isDestroyed()) {
        const [x, y] = floatWin.getPosition();
        floatWin.setPosition(x + dx, y + dy);
    }
});
ipcMain.handle('get-server-url', () => SERVER_URL);

// ═══ 第二次启动时，激活已有窗口 ═══
app.on('second-instance', () => {
    if (fullWin && !fullWin.isDestroyed()) {
        fullWin.show();
        fullWin.focus();
    } else {
        togglePanel();
    }
});

// ═══ 等待服务就绪 ═══
function waitForServer(retries = 30) {
    return new Promise((resolve) => {
        let count = 0;
        const check = () => {
            checkServer().then(ok => {
                if (ok) { resolve(true); return; }
                count++;
                if (count >= retries) { resolve(false); return; }
                setTimeout(check, 1000);
            });
        };
        check();
    });
}

// ═══ App lifecycle ═══
app.whenReady().then(async () => {
    startServer();
    createTray();
    createFloatButton();
    globalShortcut.register('Alt+D', togglePanel);
    globalShortcut.register('Alt+Shift+D', openFullWindow);
    globalShortcut.register('Alt+V', () => {
        // 语音快捷键：打开面板并触发语音录入
        createPanel();
        setTimeout(() => {
            if (panelWin && !panelWin.isDestroyed()) {
                panelWin.webContents.executeJavaScript('startVoiceFromHotkey()').catch(() => {});
            }
        }, 500);
    });

    // 等服务就绪再打开窗口
    const ok = await waitForServer();
    if (ok) {
        openFullWindow();
    } else {
        console.log('[Error] Server failed to start');
    }
});

app.on('window-all-closed', e => e?.preventDefault?.());
app.on('before-quit', () => { if (serverProcess) serverProcess.kill(); });
