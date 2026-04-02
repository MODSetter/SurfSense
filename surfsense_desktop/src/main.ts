import { app, BrowserWindow } from 'electron';
import { registerGlobalErrorHandlers, showErrorDialog } from './modules/errors';
import { startNextServer } from './modules/server';
import { createMainWindow } from './modules/window';
import { setupDeepLinks, handlePendingDeepLink } from './modules/deep-links';
import { setupAutoUpdater } from './modules/auto-updater';
import { setupMenu } from './modules/menu';
import { registerQuickAsk, unregisterQuickAsk } from './modules/quick-ask';
import { registerAutocomplete, unregisterAutocomplete } from './modules/autocomplete';
import { registerIpcHandlers } from './ipc/handlers';
import { allPermissionsGranted } from './modules/permissions';

registerGlobalErrorHandlers();

if (!setupDeepLinks()) {
  app.quit();
}

registerIpcHandlers();

function getInitialPath(): string {
  const granted = allPermissionsGranted();
  if (process.platform === 'darwin' && !granted) {
    return '/desktop/permissions';
  }
  return '/dashboard';
}

app.whenReady().then(async () => {
  setupMenu();
  try {
    await startNextServer();
  } catch (error) {
    showErrorDialog('Failed to start SurfSense', error);
    setTimeout(() => app.quit(), 0);
    return;
  }

  const initialPath = getInitialPath();
  createMainWindow(initialPath);
  registerQuickAsk();
  registerAutocomplete();
  setupAutoUpdater();

  handlePendingDeepLink();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow(getInitialPath());
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
});
