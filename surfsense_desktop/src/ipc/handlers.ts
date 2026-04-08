import { app, ipcMain, shell } from 'electron';
import { IPC_CHANNELS } from './channels';
import {
  getPermissionsStatus,
  requestAccessibility,
  requestScreenRecording,
  restartApp,
} from '../modules/permissions';
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
import { getActiveSearchSpaceId, setActiveSearchSpaceId } from '../modules/active-search-space';
import { reregisterQuickAsk } from '../modules/quick-ask';
import { reregisterAutocomplete } from '../modules/autocomplete';
import { reregisterGeneralAssist } from '../modules/tray';

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

  ipcMain.handle(IPC_CHANNELS.SET_AUTH_TOKENS, (_event, tokens: { bearer: string; refresh: string }) => {
    authTokens = tokens;
  });

  ipcMain.handle(IPC_CHANNELS.GET_AUTH_TOKENS, () => {
    return authTokens;
  });

  ipcMain.handle(IPC_CHANNELS.GET_SHORTCUTS, () => getShortcuts());

  ipcMain.handle(IPC_CHANNELS.GET_ACTIVE_SEARCH_SPACE, () => getActiveSearchSpaceId());

  ipcMain.handle(IPC_CHANNELS.SET_ACTIVE_SEARCH_SPACE, (_event, id: string) =>
    setActiveSearchSpaceId(id)
  );

  ipcMain.handle(IPC_CHANNELS.SET_SHORTCUTS, async (_event, config: Partial<ShortcutConfig>) => {
    const updated = await setShortcuts(config);
    if (config.generalAssist) await reregisterGeneralAssist();
    if (config.quickAsk) await reregisterQuickAsk();
    if (config.autocomplete) await reregisterAutocomplete();
    return updated;
  });
}
