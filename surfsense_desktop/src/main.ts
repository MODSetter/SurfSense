import { app, BrowserWindow } from 'electron';

let isQuitting = false;
import { registerGlobalErrorHandlers, showErrorDialog } from './modules/errors';
import { startNextServer } from './modules/server';
import { createMainWindow, getMainWindow } from './modules/window';
import { setupDeepLinks, handlePendingDeepLink } from './modules/deep-links';
import { setupAutoUpdater } from './modules/auto-updater';
import { setupMenu } from './modules/menu';
import { registerQuickAsk, unregisterQuickAsk } from './modules/quick-ask';
import { registerAutocomplete, unregisterAutocomplete } from './modules/autocomplete';
import { registerFolderWatcher, unregisterFolderWatcher } from './modules/folder-watcher';
import { registerIpcHandlers } from './ipc/handlers';
import { createTray, destroyTray } from './modules/tray';
import { initAnalytics, shutdownAnalytics, trackEvent } from './modules/analytics';

registerGlobalErrorHandlers();

if (!setupDeepLinks()) {
  app.quit();
}

registerIpcHandlers();

app.whenReady().then(async () => {
  initAnalytics();
  trackEvent('desktop_app_launched');
  setupMenu();
  try {
    await startNextServer();
  } catch (error) {
    showErrorDialog('Failed to start SurfSense', error);
    setTimeout(() => app.quit(), 0);
    return;
  }

  await createTray();

  const win = createMainWindow('/dashboard');

  // Minimize to tray instead of closing the app
  win.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault();
      win.hide();
    }
  });

  await registerQuickAsk();
  await registerAutocomplete();
  registerFolderWatcher();
  setupAutoUpdater();

  handlePendingDeepLink();

  app.on('activate', () => {
    const mw = getMainWindow();
    if (!mw || mw.isDestroyed()) {
      createMainWindow('/dashboard');
    } else {
      mw.show();
      mw.focus();
    }
  });
});

// Keep running in the background — the tray "Quit" calls app.exit()
app.on('window-all-closed', () => {
  // Do nothing: the app stays alive in the tray
});

app.on('before-quit', () => {
  isQuitting = true;
});

let didCleanup = false;
app.on('will-quit', async (e) => {
  if (didCleanup) return;
  didCleanup = true;
  e.preventDefault();
  unregisterQuickAsk();
  unregisterAutocomplete();
  unregisterFolderWatcher();
  destroyTray();
  await shutdownAnalytics();
  app.exit();
});
