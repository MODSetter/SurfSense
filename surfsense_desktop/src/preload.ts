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
  onDeepLink: (callback: (url: string) => void) => {
    const listener = (_event: unknown, url: string) => callback(url);
    ipcRenderer.on(IPC_CHANNELS.DEEP_LINK, listener);
    return () => {
      ipcRenderer.removeListener(IPC_CHANNELS.DEEP_LINK, listener);
    };
  },
  getQuickAskText: () => ipcRenderer.invoke(IPC_CHANNELS.QUICK_ASK_TEXT),
  setQuickAskMode: (mode: string) => ipcRenderer.invoke(IPC_CHANNELS.SET_QUICK_ASK_MODE, mode),
  getQuickAskMode: () => ipcRenderer.invoke(IPC_CHANNELS.GET_QUICK_ASK_MODE),
  replaceText: (text: string) => ipcRenderer.invoke(IPC_CHANNELS.REPLACE_TEXT, text),
  // Permissions
  getPermissionsStatus: () => ipcRenderer.invoke(IPC_CHANNELS.GET_PERMISSIONS_STATUS),
  requestAccessibility: () => ipcRenderer.invoke(IPC_CHANNELS.REQUEST_ACCESSIBILITY),
  restartApp: () => ipcRenderer.invoke(IPC_CHANNELS.RESTART_APP),
  // Autocomplete
  onAutocompleteContext: (callback: (data: { screenshot: string; searchSpaceId?: string }) => void) => {
    const listener = (_event: unknown, data: { screenshot: string; searchSpaceId?: string }) => callback(data);
    ipcRenderer.on(IPC_CHANNELS.AUTOCOMPLETE_CONTEXT, listener);
    return () => {
      ipcRenderer.removeListener(IPC_CHANNELS.AUTOCOMPLETE_CONTEXT, listener);
    };
  },
  acceptSuggestion: (text: string) => ipcRenderer.invoke(IPC_CHANNELS.ACCEPT_SUGGESTION, text),
  dismissSuggestion: () => ipcRenderer.invoke(IPC_CHANNELS.DISMISS_SUGGESTION),
  updateSuggestionText: (text: string) => ipcRenderer.invoke(IPC_CHANNELS.UPDATE_SUGGESTION_TEXT, text),
  setAutocompleteEnabled: (enabled: boolean) => ipcRenderer.invoke(IPC_CHANNELS.SET_AUTOCOMPLETE_ENABLED, enabled),
  getAutocompleteEnabled: () => ipcRenderer.invoke(IPC_CHANNELS.GET_AUTOCOMPLETE_ENABLED),
});
