import { app, ipcMain, shell } from 'electron';
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
  readAgentLocalFileText,
  writeAgentLocalFileText,
  getAgentFilesystemMounts,
  getAgentFilesystemSettings,
  pickAgentFilesystemRoot,
  setAgentFilesystemSettings,
} from '../modules/agent-filesystem';

let authTokens: { bearer: string; refresh: string } | null = null;

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

  ipcMain.handle(IPC_CHANNELS.READ_AGENT_LOCAL_FILE_TEXT, async (_event, virtualPath: string) => {
    try {
      const result = await readAgentLocalFileText(virtualPath);
      return { ok: true, path: result.path, content: result.content };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to read local file';
      return { ok: false, path: virtualPath, error: message };
    }
  });

  ipcMain.handle(
    IPC_CHANNELS.WRITE_AGENT_LOCAL_FILE_TEXT,
    async (_event, virtualPath: string, content: string) => {
      try {
        const result = await writeAgentLocalFileText(virtualPath, content);
        return { ok: true, path: result.path };
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to write local file';
        return { ok: false, path: virtualPath, error: message };
      }
    }
  );

  ipcMain.handle(IPC_CHANNELS.SET_AUTH_TOKENS, (_event, tokens: { bearer: string; refresh: string }) => {
    authTokens = tokens;
  });

  ipcMain.handle(IPC_CHANNELS.GET_AUTH_TOKENS, () => {
    return authTokens;
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

  ipcMain.handle(IPC_CHANNELS.AGENT_FILESYSTEM_GET_SETTINGS, () =>
    getAgentFilesystemSettings()
  );

  ipcMain.handle(IPC_CHANNELS.AGENT_FILESYSTEM_GET_MOUNTS, () =>
    getAgentFilesystemMounts()
  );

  ipcMain.handle(
    IPC_CHANNELS.AGENT_FILESYSTEM_SET_SETTINGS,
    (_event, settings: { mode?: 'cloud' | 'desktop_local_folder'; localRootPaths?: string[] | null }) =>
      setAgentFilesystemSettings(settings)
  );

  ipcMain.handle(IPC_CHANNELS.AGENT_FILESYSTEM_PICK_ROOT, () =>
    pickAgentFilesystemRoot()
  );
}
