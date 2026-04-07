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
  requestScreenRecording: () => ipcRenderer.invoke(IPC_CHANNELS.REQUEST_SCREEN_RECORDING),
  restartApp: () => ipcRenderer.invoke(IPC_CHANNELS.RESTART_APP),
  // Autocomplete
  onAutocompleteContext: (callback: (data: { screenshot: string; searchSpaceId?: string; appName?: string; windowTitle?: string }) => void) => {
    const listener = (_event: unknown, data: { screenshot: string; searchSpaceId?: string; appName?: string; windowTitle?: string }) => callback(data);
    ipcRenderer.on(IPC_CHANNELS.AUTOCOMPLETE_CONTEXT, listener);
    return () => {
      ipcRenderer.removeListener(IPC_CHANNELS.AUTOCOMPLETE_CONTEXT, listener);
    };
  },
  acceptSuggestion: (text: string) => ipcRenderer.invoke(IPC_CHANNELS.ACCEPT_SUGGESTION, text),
  dismissSuggestion: () => ipcRenderer.invoke(IPC_CHANNELS.DISMISS_SUGGESTION),
  setAutocompleteEnabled: (enabled: boolean) => ipcRenderer.invoke(IPC_CHANNELS.SET_AUTOCOMPLETE_ENABLED, enabled),
  getAutocompleteEnabled: () => ipcRenderer.invoke(IPC_CHANNELS.GET_AUTOCOMPLETE_ENABLED),

  // Folder sync
  selectFolder: () => ipcRenderer.invoke(IPC_CHANNELS.FOLDER_SYNC_SELECT_FOLDER),
  addWatchedFolder: (config: any) => ipcRenderer.invoke(IPC_CHANNELS.FOLDER_SYNC_ADD_FOLDER, config),
  removeWatchedFolder: (folderPath: string) => ipcRenderer.invoke(IPC_CHANNELS.FOLDER_SYNC_REMOVE_FOLDER, folderPath),
  getWatchedFolders: () => ipcRenderer.invoke(IPC_CHANNELS.FOLDER_SYNC_GET_FOLDERS),
  getWatcherStatus: () => ipcRenderer.invoke(IPC_CHANNELS.FOLDER_SYNC_GET_STATUS),
  onFileChanged: (callback: (data: any) => void) => {
    const listener = (_event: unknown, data: any) => callback(data);
    ipcRenderer.on(IPC_CHANNELS.FOLDER_SYNC_FILE_CHANGED, listener);
    return () => {
      ipcRenderer.removeListener(IPC_CHANNELS.FOLDER_SYNC_FILE_CHANGED, listener);
    };
  },
  onWatcherReady: (callback: (data: any) => void) => {
    const listener = (_event: unknown, data: any) => callback(data);
    ipcRenderer.on(IPC_CHANNELS.FOLDER_SYNC_WATCHER_READY, listener);
    return () => {
      ipcRenderer.removeListener(IPC_CHANNELS.FOLDER_SYNC_WATCHER_READY, listener);
    };
  },
  pauseWatcher: () => ipcRenderer.invoke(IPC_CHANNELS.FOLDER_SYNC_PAUSE),
  resumeWatcher: () => ipcRenderer.invoke(IPC_CHANNELS.FOLDER_SYNC_RESUME),
  signalRendererReady: () => ipcRenderer.invoke(IPC_CHANNELS.FOLDER_SYNC_RENDERER_READY),
  getPendingFileEvents: () => ipcRenderer.invoke(IPC_CHANNELS.FOLDER_SYNC_GET_PENDING_EVENTS),
  acknowledgeFileEvents: (eventIds: string[]) => ipcRenderer.invoke(IPC_CHANNELS.FOLDER_SYNC_ACK_EVENTS, eventIds),

  // Browse files via native dialog
  browseFiles: () => ipcRenderer.invoke(IPC_CHANNELS.BROWSE_FILES),
  readLocalFiles: (paths: string[]) => ipcRenderer.invoke(IPC_CHANNELS.READ_LOCAL_FILES, paths),

  // Auth token sync across windows
  getAuthTokens: () => ipcRenderer.invoke(IPC_CHANNELS.GET_AUTH_TOKENS),
  setAuthTokens: (bearer: string, refresh: string) =>
    ipcRenderer.invoke(IPC_CHANNELS.SET_AUTH_TOKENS, { bearer, refresh }),
});
