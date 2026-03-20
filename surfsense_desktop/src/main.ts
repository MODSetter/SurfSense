import { app, BrowserWindow } from 'electron';
import { registerGlobalErrorHandlers, showErrorDialog } from './modules/errors';
import { startNextServer } from './modules/server';
import { createMainWindow } from './modules/window';
import { setupDeepLinks, handlePendingDeepLink } from './modules/deep-links';
import { setupAutoUpdater } from './modules/auto-updater';
import { setupMenu } from './modules/menu';
import { setupTray } from './modules/tray';
import { registerIpcHandlers } from './ipc/handlers';
import { registerClipboardHandlers } from './modules/clipboard';

registerGlobalErrorHandlers();

if (!setupDeepLinks()) {
  app.quit();
}

registerIpcHandlers();
registerClipboardHandlers();

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
  setupTray();
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
