const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('daylife', {
    togglePanel: () => ipcRenderer.send('toggle-panel'),
    openFull: () => ipcRenderer.send('open-browser'),
    closePanel: () => ipcRenderer.send('close-panel'),
    moveFloat: (dx, dy) => ipcRenderer.send('move-float', dx, dy),
    getServerUrl: () => ipcRenderer.invoke('get-server-url'),
});
