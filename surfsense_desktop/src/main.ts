import { app, BrowserWindow, shell, ipcMain, dialog, Menu } from 'electron';
import path from 'path';
import { autoUpdater } from 'electron-updater';
import { registerGlobalErrorHandlers, showErrorDialog } from './modules/errors';
import { startNextServer, getServerPort } from './modules/server';
import { createMainWindow, getMainWindow } from './modules/window';

registerGlobalErrorHandlers();

const isDev = !app.isPackaged;
let deepLinkUrl: string | null = null;

const PROTOCOL = 'surfsense';

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

// Deep link handling
function handleDeepLink(url: string) {
  if (!url.startsWith(`${PROTOCOL}://`)) return;

  deepLinkUrl = url;

  const win = getMainWindow();
  if (!win) return;

  const parsed = new URL(url);
  if (parsed.hostname === 'auth' && parsed.pathname === '/callback') {
    const params = parsed.searchParams.toString();
    win.loadURL(`http://localhost:${getServerPort()}/auth/callback?${params}`);
  }

  win.show();
  win.focus();
}

// Single instance lock — second instance passes deep link to first
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', (_event, argv) => {
    // Windows/Linux: deep link URL is in argv
    const url = argv.find((arg) => arg.startsWith(`${PROTOCOL}://`));
    if (url) handleDeepLink(url);

    const win = getMainWindow();
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });
}

// macOS: deep link arrives via open-url event
app.on('open-url', (event, url) => {
  event.preventDefault();
  handleDeepLink(url);
});

// Register surfsense:// protocol
if (process.defaultApp) {
  if (process.argv.length >= 2) {
    app.setAsDefaultProtocolClient(PROTOCOL, process.execPath, [path.resolve(process.argv[1])]);
  }
} else {
  app.setAsDefaultProtocolClient(PROTOCOL);
}

function setupAutoUpdater() {
  if (isDev) return;

  autoUpdater.autoDownload = true;

  autoUpdater.on('update-available', (info) => {
    console.log(`Update available: ${info.version}`);
  });

  autoUpdater.on('update-downloaded', (info) => {
    console.log(`Update downloaded: ${info.version}`);
    dialog.showMessageBox({
      type: 'info',
      buttons: ['Restart', 'Later'],
      defaultId: 0,
      title: 'Update Ready',
      message: `Version ${info.version} has been downloaded. Restart to apply the update.`,
    }).then(({ response }) => {
      if (response === 0) {
        autoUpdater.quitAndInstall();
      }
    });
  });

  autoUpdater.on('error', (err) => {
    console.error('Auto-updater error:', err);
  });

  autoUpdater.checkForUpdates();
}

function setupMenu() {
  const isMac = process.platform === 'darwin';
  const template: Electron.MenuItemConstructorOptions[] = [
    ...(isMac ? [{ role: 'appMenu' as const }] : []),
    { role: 'fileMenu' as const },
    { role: 'editMenu' as const },
    { role: 'viewMenu' as const },
    { role: 'windowMenu' as const },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

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

  // If a deep link was received before the window was ready, handle it now
  if (deepLinkUrl) {
    handleDeepLink(deepLinkUrl);
    deepLinkUrl = null;
  }

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
