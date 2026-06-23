import { app, BrowserWindow, ipcMain, shell } from 'electron';
import { IPC_CHANNELS } from './channels';
import {
  getPermissionsStatus,
  hasScreenRecordingPermission,
  requestAccessibility,
  requestScreenRecording,
  restartApp,
} from '../modules/permissions';
import { pickOpenWindowCapture } from '../modules/screen-capture';
import {
  selectFolder,
  addWatchedFolder,
  removeWatchedFolder,
  getWatchedFolders,
  getWatcherStatus,
  getPendingFileEvents,
  acknowledgeFileEvents,
  pauseWatcher,
  resumeWatcher,
  markRendererReady,
  browseFiles,
  readLocalFiles,
  listFolderFiles,
  seedFolderMtimes,
  type WatchedFolderConfig,
} from '../modules/folder-watcher';
import { getShortcuts, setShortcuts, type ShortcutConfig } from '../modules/shortcuts';
import { getAutoLaunchState, setAutoLaunch } from '../modules/auto-launch';
import { getActiveSearchSpaceId, setActiveSearchSpaceId } from '../modules/active-search-space';
import { reregisterQuickAsk } from '../modules/quick-ask';
import { reregisterGeneralAssist, reregisterScreenshotAssist } from '../modules/tray';
import {
  getDistinctId,
  getMachineId,
  identifyUser as analyticsIdentify,
  resetUser as analyticsReset,
  trackEvent,
} from '../modules/analytics';
import {
  listAgentFilesystemFiles,
  readAgentLocalFileText,
  writeAgentLocalFileText,
  getAgentFilesystemMounts,
  getAgentFilesystemSettings,
  pickAgentFilesystemRoot,
  setAgentFilesystemSettings,
} from '../modules/agent-filesystem';
import {
  startAgentFilesystemTreeWatch,
  stopAgentFilesystemTreeWatch,
  type AgentFilesystemTreeWatchOptions,
} from '../modules/agent-filesystem-tree-watcher';
import { installDownloadedUpdate } from '../modules/auto-updater';
import { secretStore } from '../modules/secret-store';
import { startGoogleOAuth } from '../modules/oauth';

const REFRESH_TOKEN_KEY = 'surfsense_refresh_token';
let accessToken: string | null = null;
let refreshInFlight: Promise<string | null> | null = null;

function getBackendUrl(): string {
  return (process.env.HOSTED_BACKEND_URL || process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || '').replace(
    /\/+$/,
    ''
  );
}

function broadcastAuthChanged(): void {
  for (const win of BrowserWindow.getAllWindows()) {
    win.webContents.send(IPC_CHANNELS.AUTH_CHANGED, { authed: !!accessToken, accessToken });
  }
}

async function storeTokens(tokens: { bearer: string; refresh?: string | null }): Promise<void> {
  accessToken = tokens.bearer || null;
  if (tokens.refresh) {
    await secretStore.set(REFRESH_TOKEN_KEY, tokens.refresh);
  }
  broadcastAuthChanged();
}

async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    const refresh = await secretStore.get(REFRESH_TOKEN_KEY);
    const backendUrl = getBackendUrl();
    if (!refresh || !backendUrl) return null;

    const response = await fetch(`${backendUrl}/auth/jwt/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!response.ok) return null;

    const data = (await response.json()) as { access_token?: string; refresh_token?: string | null };
    if (!data.access_token) return null;
    await storeTokens({ bearer: data.access_token, refresh: data.refresh_token });
    return data.access_token;
  })().finally(() => {
    refreshInFlight = null;
  });

  return refreshInFlight;
}

export function registerIpcHandlers(): void {
  ipcMain.on(IPC_CHANNELS.OPEN_EXTERNAL, (_event, url: string) => {
    try {
      const parsed = new URL(url);
      if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
        shell.openExternal(url);
      }
    } catch {
      // invalid URL — ignore
    }
  });

  ipcMain.handle(IPC_CHANNELS.GET_APP_VERSION, () => {
    return app.getVersion();
  });

  ipcMain.handle(IPC_CHANNELS.UPDATE_INSTALL_NOW, () => {
    installDownloadedUpdate();
  });

  ipcMain.handle(IPC_CHANNELS.GET_PERMISSIONS_STATUS, () => {
    return getPermissionsStatus();
  });

  ipcMain.handle(IPC_CHANNELS.REQUEST_ACCESSIBILITY, () => {
    requestAccessibility();
  });

  ipcMain.handle(IPC_CHANNELS.REQUEST_SCREEN_RECORDING, () => {
    requestScreenRecording();
  });

  ipcMain.handle(IPC_CHANNELS.RESTART_APP, () => {
    restartApp();
  });

  ipcMain.handle(IPC_CHANNELS.CAPTURE_FULL_SCREEN, async () => {
    if (!hasScreenRecordingPermission()) {
      requestScreenRecording();
      return null;
    }
    const picked = await pickOpenWindowCapture();
    return picked?.dataUrl ?? null;
  });

  // Folder sync handlers
  ipcMain.handle(IPC_CHANNELS.FOLDER_SYNC_SELECT_FOLDER, () => selectFolder());

  ipcMain.handle(IPC_CHANNELS.FOLDER_SYNC_ADD_FOLDER, (_event, config) =>
    addWatchedFolder(config)
  );

  ipcMain.handle(IPC_CHANNELS.FOLDER_SYNC_REMOVE_FOLDER, (_event, folderPath: string) =>
    removeWatchedFolder(folderPath)
  );

  ipcMain.handle(IPC_CHANNELS.FOLDER_SYNC_GET_FOLDERS, () => getWatchedFolders());

  ipcMain.handle(IPC_CHANNELS.FOLDER_SYNC_GET_STATUS, () => getWatcherStatus());

  ipcMain.handle(IPC_CHANNELS.FOLDER_SYNC_PAUSE, () => pauseWatcher());

  ipcMain.handle(IPC_CHANNELS.FOLDER_SYNC_RESUME, () => resumeWatcher());

  ipcMain.handle(IPC_CHANNELS.FOLDER_SYNC_RENDERER_READY, () => {
    markRendererReady();
  });

  ipcMain.handle(IPC_CHANNELS.FOLDER_SYNC_GET_PENDING_EVENTS, () =>
    getPendingFileEvents()
  );

  ipcMain.handle(IPC_CHANNELS.FOLDER_SYNC_ACK_EVENTS, (_event, eventIds: string[]) =>
    acknowledgeFileEvents(eventIds)
  );

  ipcMain.handle(IPC_CHANNELS.FOLDER_SYNC_LIST_FILES, (_event, config: WatchedFolderConfig) =>
    listFolderFiles(config)
  );

  ipcMain.handle(
    IPC_CHANNELS.FOLDER_SYNC_SEED_MTIMES,
    (_event, folderPath: string, mtimes: Record<string, number>) =>
      seedFolderMtimes(folderPath, mtimes),
  );

  ipcMain.handle(IPC_CHANNELS.BROWSE_FILES, () => browseFiles());

  ipcMain.handle(IPC_CHANNELS.READ_LOCAL_FILES, (_event, paths: string[]) =>
    readLocalFiles(paths)
  );

  ipcMain.handle(
    IPC_CHANNELS.READ_AGENT_LOCAL_FILE_TEXT,
    async (_event, virtualPath: string, searchSpaceId?: number | null) => {
    try {
      const result = await readAgentLocalFileText(virtualPath, searchSpaceId);
      return { ok: true, path: result.path, content: result.content };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to read local file';
      return { ok: false, path: virtualPath, error: message };
    }
    }
  );

  ipcMain.handle(
    IPC_CHANNELS.WRITE_AGENT_LOCAL_FILE_TEXT,
    async (_event, virtualPath: string, content: string, searchSpaceId?: number | null) => {
      try {
        const result = await writeAgentLocalFileText(virtualPath, content, searchSpaceId);
        return { ok: true, path: result.path };
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to write local file';
        return { ok: false, path: virtualPath, error: message };
      }
    }
  );

  ipcMain.handle(IPC_CHANNELS.SET_AUTH_TOKENS, async (_event, tokens: { bearer: string; refresh: string }) => {
    await storeTokens(tokens);
  });

  ipcMain.handle(IPC_CHANNELS.GET_AUTH_TOKENS, async () => {
    if (!accessToken) {
      await refreshAccessToken();
    }
    return accessToken ? { bearer: accessToken, refresh: '' } : null;
  });

  ipcMain.handle(IPC_CHANNELS.GET_ACCESS_TOKEN, async () => {
    if (!accessToken) {
      await refreshAccessToken();
    }
    return accessToken;
  });

  ipcMain.handle(IPC_CHANNELS.REFRESH_ACCESS_TOKEN, () => {
    return refreshAccessToken();
  });

  ipcMain.handle(IPC_CHANNELS.LOGOUT, async () => {
    const backendUrl = getBackendUrl();
    const refresh = await secretStore.get(REFRESH_TOKEN_KEY);
    if (backendUrl && refresh) {
      try {
        await fetch(`${backendUrl}/auth/jwt/revoke`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refresh }),
        });
      } catch {
        // Local logout is fail-closed even if the server revoke call fails.
      }
    }
    accessToken = null;
    await secretStore.clear(REFRESH_TOKEN_KEY);
    broadcastAuthChanged();
  });

  ipcMain.handle(IPC_CHANNELS.AUTH_START_GOOGLE, async () => {
    const backendUrl = getBackendUrl();
    if (!backendUrl) {
      throw new Error('Backend URL is not configured');
    }
    const tokens = await startGoogleOAuth(backendUrl);
    await storeTokens({ bearer: tokens.access_token, refresh: tokens.refresh_token });
    return { ok: true };
  });

  ipcMain.handle(IPC_CHANNELS.GET_SHORTCUTS, () => getShortcuts());

  ipcMain.handle(IPC_CHANNELS.GET_AUTO_LAUNCH, () => getAutoLaunchState());

  ipcMain.handle(
    IPC_CHANNELS.SET_AUTO_LAUNCH,
    async (_event, payload: { enabled: boolean; openAsHidden?: boolean }) => {
      const next = await setAutoLaunch(payload.enabled, payload.openAsHidden);
      trackEvent('desktop_auto_launch_toggled', {
        enabled: next.enabled,
        open_as_hidden: next.openAsHidden,
        supported: next.supported,
      });
      return next;
    },
  );

  ipcMain.handle(IPC_CHANNELS.GET_ACTIVE_SEARCH_SPACE, () => getActiveSearchSpaceId());

  ipcMain.handle(IPC_CHANNELS.SET_ACTIVE_SEARCH_SPACE, (_event, id: string) =>
    setActiveSearchSpaceId(id)
  );

  ipcMain.handle(IPC_CHANNELS.SET_SHORTCUTS, async (_event, config: Partial<ShortcutConfig>) => {
    const updated = await setShortcuts(config);
    if (config.generalAssist) await reregisterGeneralAssist();
    if (config.screenshotAssist) await reregisterScreenshotAssist();
    if (config.quickAsk) await reregisterQuickAsk();
    trackEvent('desktop_shortcut_updated', {
      keys: Object.keys(config),
    });
    return updated;
  });

  // Analytics bridge — the renderer (web UI) hands the logged-in user down
  // to the main process so desktop-only events are attributed to the same
  // PostHog person, not just an anonymous machine ID.
  ipcMain.handle(
    IPC_CHANNELS.ANALYTICS_IDENTIFY,
    (_event, payload: { userId: string; properties?: Record<string, unknown> }) => {
      if (!payload?.userId) return;
      analyticsIdentify(String(payload.userId), payload.properties);
    }
  );

  ipcMain.handle(IPC_CHANNELS.ANALYTICS_RESET, () => {
    analyticsReset();
  });

  ipcMain.handle(
    IPC_CHANNELS.ANALYTICS_CAPTURE,
    (_event, payload: { event: string; properties?: Record<string, unknown> }) => {
      if (!payload?.event) return;
      trackEvent(payload.event, payload.properties);
    }
  );

  ipcMain.handle(IPC_CHANNELS.ANALYTICS_GET_CONTEXT, () => {
    return {
      distinctId: getDistinctId(),
      machineId: getMachineId(),
      appVersion: app.getVersion(),
      platform: process.platform,
    };
  });

  ipcMain.handle(IPC_CHANNELS.AGENT_FILESYSTEM_GET_SETTINGS, (_event, searchSpaceId?: number | null) =>
    getAgentFilesystemSettings(searchSpaceId)
  );

  ipcMain.handle(IPC_CHANNELS.AGENT_FILESYSTEM_GET_MOUNTS, (_event, searchSpaceId?: number | null) =>
    getAgentFilesystemMounts(searchSpaceId)
  );

  ipcMain.handle(
    IPC_CHANNELS.AGENT_FILESYSTEM_LIST_FILES,
    (
      _event,
      options: {
        rootPath: string;
        searchSpaceId?: number | null;
        excludePatterns?: string[] | null;
        fileExtensions?: string[] | null;
      }
    ) =>
      listAgentFilesystemFiles(options)
  );

  ipcMain.handle(
    IPC_CHANNELS.AGENT_FILESYSTEM_SET_SETTINGS,
    (
      _event,
      payload: {
        searchSpaceId?: number | null;
        settings: { mode?: 'cloud' | 'desktop_local_folder'; localRootPaths?: string[] | null };
      }
    ) => setAgentFilesystemSettings(payload?.searchSpaceId, payload?.settings ?? {})
  );

  ipcMain.handle(IPC_CHANNELS.AGENT_FILESYSTEM_PICK_ROOT, () =>
    pickAgentFilesystemRoot()
  );

  ipcMain.handle(
    IPC_CHANNELS.AGENT_FILESYSTEM_TREE_WATCH_START,
    (_event, options: AgentFilesystemTreeWatchOptions) =>
      startAgentFilesystemTreeWatch(options)
  );

  ipcMain.handle(
    IPC_CHANNELS.AGENT_FILESYSTEM_TREE_WATCH_STOP,
    (_event, searchSpaceId?: number | null) =>
      stopAgentFilesystemTreeWatch(searchSpaceId)
  );
}
