import { app, ipcMain, shell } from 'electron';
import { IPC_CHANNELS } from './channels';
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
} from '../modules/folder-watcher';

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

  ipcMain.handle(IPC_CHANNELS.BROWSE_FILES, () => browseFiles());

  ipcMain.handle(IPC_CHANNELS.READ_LOCAL_FILES, (_event, paths: string[]) =>
    readLocalFiles(paths)
  );
}
