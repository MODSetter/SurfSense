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
  listFolderFiles: (config: any) => ipcRenderer.invoke(IPC_CHANNELS.FOLDER_SYNC_LIST_FILES, config),
  seedFolderMtimes: (folderPath: string, mtimes: Record<string, number>) =>
    ipcRenderer.invoke(IPC_CHANNELS.FOLDER_SYNC_SEED_MTIMES, folderPath, mtimes),

  // Browse files via native dialog
  browseFiles: () => ipcRenderer.invoke(IPC_CHANNELS.BROWSE_FILES),
  readLocalFiles: (paths: string[]) => ipcRenderer.invoke(IPC_CHANNELS.READ_LOCAL_FILES, paths),
  readAgentLocalFileText: (virtualPath: string, searchSpaceId?: number | null) =>
    ipcRenderer.invoke(IPC_CHANNELS.READ_AGENT_LOCAL_FILE_TEXT, virtualPath, searchSpaceId),
  writeAgentLocalFileText: (virtualPath: string, content: string, searchSpaceId?: number | null) =>
    ipcRenderer.invoke(IPC_CHANNELS.WRITE_AGENT_LOCAL_FILE_TEXT, virtualPath, content, searchSpaceId),

  // Auth token sync across windows
  getAuthTokens: () => ipcRenderer.invoke(IPC_CHANNELS.GET_AUTH_TOKENS),
  setAuthTokens: (bearer: string, refresh: string) =>
    ipcRenderer.invoke(IPC_CHANNELS.SET_AUTH_TOKENS, { bearer, refresh }),

  // Keyboard shortcut configuration
  getShortcuts: () => ipcRenderer.invoke(IPC_CHANNELS.GET_SHORTCUTS),
  setShortcuts: (config: Record<string, string>) =>
    ipcRenderer.invoke(IPC_CHANNELS.SET_SHORTCUTS, config),

  // Launch on system startup
  getAutoLaunch: () => ipcRenderer.invoke(IPC_CHANNELS.GET_AUTO_LAUNCH),
  setAutoLaunch: (enabled: boolean, openAsHidden?: boolean) =>
    ipcRenderer.invoke(IPC_CHANNELS.SET_AUTO_LAUNCH, { enabled, openAsHidden }),

  // Active search space
  getActiveSearchSpace: () => ipcRenderer.invoke(IPC_CHANNELS.GET_ACTIVE_SEARCH_SPACE),
  setActiveSearchSpace: (id: string) =>
    ipcRenderer.invoke(IPC_CHANNELS.SET_ACTIVE_SEARCH_SPACE, id),

  // Analytics bridge — lets posthog-js running inside the Next.js renderer
  // mirror identify/reset/capture into the Electron main-process PostHog
  // client so desktop-only events are attributed to the logged-in user.
  analyticsIdentify: (userId: string, properties?: Record<string, unknown>) =>
    ipcRenderer.invoke(IPC_CHANNELS.ANALYTICS_IDENTIFY, { userId, properties }),
  analyticsReset: () => ipcRenderer.invoke(IPC_CHANNELS.ANALYTICS_RESET),
  analyticsCapture: (event: string, properties?: Record<string, unknown>) =>
    ipcRenderer.invoke(IPC_CHANNELS.ANALYTICS_CAPTURE, { event, properties }),
  getAnalyticsContext: () => ipcRenderer.invoke(IPC_CHANNELS.ANALYTICS_GET_CONTEXT),
  // Agent filesystem mode
  getAgentFilesystemSettings: (searchSpaceId?: number | null) =>
    ipcRenderer.invoke(IPC_CHANNELS.AGENT_FILESYSTEM_GET_SETTINGS, searchSpaceId),
  getAgentFilesystemMounts: (searchSpaceId?: number | null) =>
    ipcRenderer.invoke(IPC_CHANNELS.AGENT_FILESYSTEM_GET_MOUNTS, searchSpaceId),
  listAgentFilesystemFiles: (options: {
    rootPath: string;
    searchSpaceId?: number | null;
    excludePatterns?: string[] | null;
    fileExtensions?: string[] | null;
  }) => ipcRenderer.invoke(IPC_CHANNELS.AGENT_FILESYSTEM_LIST_FILES, options),
  startAgentFilesystemTreeWatch: (options: {
    searchSpaceId?: number | null;
    rootPaths: string[];
    excludePatterns?: string[] | null;
    fileExtensions?: string[] | null;
  }) => ipcRenderer.invoke(IPC_CHANNELS.AGENT_FILESYSTEM_TREE_WATCH_START, options),
  stopAgentFilesystemTreeWatch: (searchSpaceId?: number | null) =>
    ipcRenderer.invoke(IPC_CHANNELS.AGENT_FILESYSTEM_TREE_WATCH_STOP, searchSpaceId),
  onAgentFilesystemTreeDirty: (
    callback: (data: {
      searchSpaceId: number | null;
      reason: 'watcher_event' | 'safety_poll';
      rootPath: string;
      changedPath: string | null;
      timestamp: number;
    }) => void
  ) => {
    const listener = (
      _event: unknown,
      data: {
        searchSpaceId: number | null;
        reason: 'watcher_event' | 'safety_poll';
        rootPath: string;
        changedPath: string | null;
        timestamp: number;
      }
    ) => callback(data);
    ipcRenderer.on(IPC_CHANNELS.AGENT_FILESYSTEM_TREE_DIRTY, listener);
    return () => {
      ipcRenderer.removeListener(IPC_CHANNELS.AGENT_FILESYSTEM_TREE_DIRTY, listener);
    };
  },
  setAgentFilesystemSettings: (settings: {
    mode?: "cloud" | "desktop_local_folder";
    localRootPaths?: string[] | null;
  }, searchSpaceId?: number | null) =>
    ipcRenderer.invoke(IPC_CHANNELS.AGENT_FILESYSTEM_SET_SETTINGS, { searchSpaceId, settings }),
  pickAgentFilesystemRoot: () => ipcRenderer.invoke(IPC_CHANNELS.AGENT_FILESYSTEM_PICK_ROOT),
});
