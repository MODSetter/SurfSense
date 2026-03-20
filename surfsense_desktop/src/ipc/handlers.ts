import { app, ipcMain, shell } from 'electron';
import { IPC_CHANNELS } from './channels';

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
}
