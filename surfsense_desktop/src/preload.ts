const { contextBridge, ipcRenderer } = require('electron');
const { IPC_CHANNELS } = require('./ipc/channels');

contextBridge.exposeInMainWorld('electronAPI', {
  versions: {
    electron: process.versions.electron,
    node: process.versions.node,
    chrome: process.versions.chrome,
    platform: process.platform,
  },
  openExternal: (url: string) => ipcRenderer.send(IPC_CHANNELS.OPEN_EXTERNAL, url),
  getAppVersion: () => ipcRenderer.invoke(IPC_CHANNELS.GET_APP_VERSION),
  getClipboardContent: () => ipcRenderer.invoke(IPC_CHANNELS.GET_CLIPBOARD_CONTENT),
  onDeepLink: (callback: (url: string) => void) => {
    const listener = (_event: unknown, url: string) => callback(url);
    ipcRenderer.on(IPC_CHANNELS.DEEP_LINK, listener);
    return () => {
      ipcRenderer.removeListener(IPC_CHANNELS.DEEP_LINK, listener);
    };
  },
});
