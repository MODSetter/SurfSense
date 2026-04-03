import { app, ipcMain, shell } from 'electron';
import { IPC_CHANNELS } from './channels';
import {
  getPermissionsStatus,
  requestAccessibility,
  requestScreenRecording,
  restartApp,
} from '../modules/permissions';

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
}
