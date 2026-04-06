const { app, BrowserWindow, Tray, Menu, globalShortcut, ipcMain, screen, nativeImage } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const http = require('http');

// ====== App identity ======
app.setName('DayLife');
app.setAppUserModelId('com.DayLife.dev');

// ====== Single instance lock ======
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
    app.quit();
}

let floatWin = null;
let panelWin = null;
let fullWin = null;
let tray = null;
let serverProcess = null;
let serverRestarts = 0;
const MAX_RESTARTS = 5;
const PORT = 8263;
const SERVER_URL = `http://127.0.0.1:${PORT}`;

// ====== Server log file ======
const LOG_DIR = path.join(app.getPath('userData'), 'logs');
function getLogStream() {
    if (!fs.existsSync(LOG_DIR)) fs.mkdirSync(LOG_DIR, { recursive: true });
    const logFile = path.join(LOG_DIR, 'server.log');
    // Rotate: if log > 2MB, rename to .old
    try {
        const stat = fs.statSync(logFile);
        if (stat.size > 2 * 1024 * 1024) {
            fs.renameSync(logFile, logFile + '.old');
        }
    } catch {}
    return fs.openSync(logFile, 'a');
}

function logServer(msg) {
    const ts = new Date().toISOString();
    const line = `[${ts}] ${msg}\n`;
    console.log(line.trim());
    try {
        fs.appendFileSync(path.join(LOG_DIR, 'server.log'), line);
    } catch {}
}

// ====== Start backend server ======
function startServer() {
    checkServer().then(running => {
        if (running) {
            logServer('[Server] Already running on port ' + PORT);
            return;
        }
        _spawnServer();
    });
}

function _spawnServer() {
    const daylifeExe = path.join(
        process.env.APPDATA, 'Python', 'Python313', 'Scripts', 'daylife.exe'
    );

    const logFd = getLogStream();

    logServer(`[Server] Starting: ${daylifeExe} serve --port ${PORT}`);
    serverProcess = spawn(daylifeExe, ['serve', '--port', String(PORT)], {
        stdio: ['ignore', logFd, logFd],
        detached: false,
    });

    serverProcess.on('error', (err) => {
        logServer(`[Server] Spawn error: ${err.message}, trying python fallback`);
        serverProcess = spawn('python', ['-m', 'uvicorn', 'daylife.api.main:app',
            '--host', '127.0.0.1', '--port', String(PORT)], {
            stdio: ['ignore', logFd, logFd],
            env: { ...process.env, PYTHONPATH: path.join(__dirname, '..', 'src') },
        });
        _attachExitHandler(serverProcess, logFd);
    });

    _attachExitHandler(serverProcess, logFd);
    logServer('[Server] Process spawned, PID: ' + (serverProcess.pid || 'unknown'));
}

function _attachExitHandler(proc, logFd) {
    proc.on('exit', (code, signal) => {
        logServer(`[Server] Exited with code=${code} signal=${signal}`);
        try { fs.closeSync(logFd); } catch {}

        if (serverRestarts < MAX_RESTARTS) {
            serverRestarts++;
            const delay = Math.min(2000 * serverRestarts, 10000);
            logServer(`[Server] Auto-restart #${serverRestarts} in ${delay}ms`);
            setTimeout(() => {
                checkServer().then(running => {
                    if (!running) _spawnServer();
                    else logServer('[Server] Already recovered');
                });
            }, delay);
        } else {
            logServer(`[Server] Max restarts (${MAX_RESTARTS}) reached, giving up`);
        }
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

// ====== Icon ======
function getIconPath() {
    return path.join(__dirname, 'icon.ico');
}
function getIcon() {
    return nativeImage.createFromPath(path.join(__dirname, 'icon.png'));
}

// ====== Float button ======
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

// ====== Quick panel ======
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

// ====== Full calendar window ======
function openFullWindow() {
    if (fullWin && !fullWin.isDestroyed()) {
        fullWin.show(); fullWin.focus(); return;
    }
    fullWin = new BrowserWindow({
        width: 1400, height: 900,
        icon: getIconPath(),
        title: 'DayLife - \u6BCF\u65E5\u8BB0\u5F55',
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

// ====== System tray ======
function createTray() {
    tray = new Tray(getIcon());
    tray.setToolTip('DayLife - \u6BCF\u65E5\u8BB0\u5F55');
    tray.setContextMenu(Menu.buildFromTemplate([
        { label: '\u6253\u5F00\u9762\u677F', click: togglePanel },
        { label: '\u5B8C\u6574\u65E5\u5386', click: openFullWindow },
        { type: 'separator' },
        { label: '\u663E\u793A\u60AC\u6D6E\u7403', click: () => floatWin?.show() },
        { label: '\u9690\u85CF\u60AC\u6D6E\u7403', click: () => floatWin?.hide() },
        { type: 'separator' },
        { label: '\u91CD\u542F\u540E\u7AEF', click: () => {
            logServer('[Server] Manual restart requested');
            serverRestarts = 0;
            if (serverProcess) serverProcess.kill();
            setTimeout(() => startServer(), 1000);
        }},
        { type: 'separator' },
        { label: '\u9000\u51FA DayLife', click: () => {
            if (serverProcess) serverProcess.kill();
            app.exit(0);
        }},
    ]));
    tray.on('click', togglePanel);
    tray.on('double-click', openFullWindow);
}

// ====== Zoom support ======
function enableZoom(win) {
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
    win.webContents.on('zoom-changed', (event, direction) => {
        const z = win.webContents.getZoomFactor();
        if (direction === 'in') win.webContents.setZoomFactor(Math.min(z + 0.1, 3));
        else win.webContents.setZoomFactor(Math.max(z - 0.1, 0.5));
    });
}

// ====== IPC ======
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

// ====== Second instance ======
app.on('second-instance', () => {
    if (fullWin && !fullWin.isDestroyed()) {
        fullWin.show();
        fullWin.focus();
    } else {
        togglePanel();
    }
});

// ====== Wait for server ready ======
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

// ====== App lifecycle ======
app.whenReady().then(async () => {
    startServer();
    createTray();
    createFloatButton();
    globalShortcut.register('Alt+D', togglePanel);
    globalShortcut.register('Alt+Shift+D', openFullWindow);
    globalShortcut.register('Alt+V', () => {
        createPanel();
        setTimeout(() => {
            if (panelWin && !panelWin.isDestroyed()) {
                panelWin.webContents.executeJavaScript('startVoiceFromHotkey()').catch(() => {});
            }
        }, 500);
    });

    const ok = await waitForServer();
    if (ok) {
        logServer('[App] Server ready, opening full window');
        openFullWindow();
    } else {
        logServer('[App] Server failed to start after 30 retries');
    }
});

app.on('window-all-closed', e => e?.preventDefault?.());
app.on('before-quit', () => { if (serverProcess) serverProcess.kill(); });
