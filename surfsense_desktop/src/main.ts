import { app, BrowserWindow } from 'electron';
import { registerGlobalErrorHandlers, showErrorDialog } from './modules/errors';
import { startNextServer } from './modules/server';
import { createMainWindow } from './modules/window';
import { setupDeepLinks, handlePendingDeepLink } from './modules/deep-links';
import { setupAutoUpdater } from './modules/auto-updater';
import { setupMenu } from './modules/menu';
import { registerQuickAsk, unregisterQuickAsk } from './modules/quick-ask';
import { registerAutocomplete, unregisterAutocomplete } from './modules/autocomplete';
import { registerFolderWatcher, unregisterFolderWatcher } from './modules/folder-watcher';
import { registerIpcHandlers } from './ipc/handlers';

registerGlobalErrorHandlers();

if (!setupDeepLinks()) {
  app.quit();
}

registerIpcHandlers();

app.whenReady().then(async () => {
  setupMenu();
  try {
    await startNextServer();
  } catch (error) {
    showErrorDialog('Failed to start SurfSense', error);
    setTimeout(() => app.quit(), 0);
    return;
  }

  createMainWindow('/dashboard');
  registerQuickAsk();
  registerAutocomplete();
  registerFolderWatcher();
  setupAutoUpdater();

  handlePendingDeepLink();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow('/dashboard');
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  unregisterQuickAsk();
  unregisterAutocomplete();
  unregisterFolderWatcher();
});
