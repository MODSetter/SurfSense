import { app } from 'electron';

import { registerGlobalErrorHandlers, showErrorDialog } from './modules/errors';
import { startNextServer } from './modules/server';
import { createMainWindow, getMainWindow, markQuitting } from './modules/window';
import { setupDeepLinks, handlePendingDeepLink, hasPendingDeepLink } from './modules/deep-links';
import { setupAutoUpdater } from './modules/auto-updater';
import { setupMenu } from './modules/menu';
import { registerQuickAsk, unregisterQuickAsk } from './modules/quick-ask';
import { registerFolderWatcher, unregisterFolderWatcher } from './modules/folder-watcher';
import { registerIpcHandlers } from './ipc/handlers';
import { createTray, destroyTray } from './modules/tray';
import { initAnalytics, shutdownAnalytics, trackEvent } from './modules/analytics';
import {
  applyAutoLaunchDefaults,
  shouldStartHidden,
  syncAutoLaunchOnStartup,
  wasLaunchedAtLogin,
} from './modules/auto-launch';

registerGlobalErrorHandlers();

if (!setupDeepLinks()) {
  app.quit();
}

registerIpcHandlers();

app.whenReady().then(async () => {
  initAnalytics();
  const launchedAtLogin = wasLaunchedAtLogin();
  const startedHidden = shouldStartHidden();
  trackEvent('desktop_app_launched', {
    launched_at_login: launchedAtLogin,
    started_hidden: startedHidden,
  });
  setupMenu();
  try {
    await startNextServer();
  } catch (error) {
    showErrorDialog('Failed to start SurfSense', error);
    setTimeout(() => app.quit(), 0);
    return;
  }

  await createTray();
  const defaultsApplied = await applyAutoLaunchDefaults();
  if (defaultsApplied) {
    trackEvent('desktop_auto_launch_defaulted_on');
  }
  await syncAutoLaunchOnStartup();

  // When started by the OS at login we stay quietly in the tray. The window
  // is created lazily on first user interaction (tray click / activate).
  // Exception: if a deep link is queued, the user explicitly asked to land
  // in the app — don't swallow it.
  if (!startedHidden || hasPendingDeepLink()) {
    createMainWindow('/dashboard');
  }

  await registerQuickAsk();
  registerFolderWatcher();
  setupAutoUpdater();

  handlePendingDeepLink();

  app.on('activate', () => {
    const mw = getMainWindow();
    trackEvent('desktop_app_activated');
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
  markQuitting();
  trackEvent('desktop_app_quit');
});

let didCleanup = false;
app.on('will-quit', async (e) => {
  if (didCleanup) return;
  didCleanup = true;
  e.preventDefault();
  unregisterQuickAsk();
  unregisterFolderWatcher();
  destroyTray();
  await shutdownAnalytics();
  app.exit();
});
