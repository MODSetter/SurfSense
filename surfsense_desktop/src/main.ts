import { app, BrowserWindow, shell, ipcMain } from 'electron';
import { registerGlobalErrorHandlers, showErrorDialog } from './modules/errors';
import { startNextServer } from './modules/server';
import { createMainWindow } from './modules/window';
import { setupDeepLinks, handlePendingDeepLink } from './modules/deep-links';
import { setupAutoUpdater } from './modules/auto-updater';
import { setupMenu } from './modules/menu';

registerGlobalErrorHandlers();

if (!setupDeepLinks()) {
  app.quit();
}

// IPC handlers
ipcMain.on('open-external', (_event, url: string) => {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      shell.openExternal(url);
    }
  } catch {
    // invalid URL — ignore
  }
});

ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});

// App lifecycle
app.whenReady().then(async () => {
  setupMenu();
  try {
    await startNextServer();
  } catch (error) {
    showErrorDialog('Failed to start SurfSense', error);
    setTimeout(() => app.quit(), 0);
    return;
  }
  createMainWindow();
  setupAutoUpdater();

  handlePendingDeepLink();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  // Server runs in-process — no child process to kill
});
