import { app, BrowserWindow, shell, session } from 'electron';
import path from 'path';
import { trackEvent } from './analytics';
import { showErrorDialog } from './errors';
import { getServerPort } from './server';
import { setActiveSearchSpaceId } from './active-search-space';

const isDev = !app.isPackaged;
const HOSTED_FRONTEND_URL = process.env.HOSTED_FRONTEND_URL as string;

let mainWindow: BrowserWindow | null = null;
let isQuitting = false;

export function getMainWindow(): BrowserWindow | null {
  return mainWindow;
}

// Called from main.ts on `before-quit` so the close-to-tray handler knows
// to actually let the window die instead of hiding it.
export function markQuitting(): void {
  isQuitting = true;
}

export function createMainWindow(initialPath = '/dashboard'): BrowserWindow {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webviewTag: false,
    },
    show: false,
    titleBarStyle: 'hiddenInset',
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  mainWindow.loadURL(`http://localhost:${getServerPort()}${initialPath}`);

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://localhost')) {
      return { action: 'allow' };
    }
    shell.openExternal(url);
    return { action: 'deny' };
  });

  const filter = { urls: [`${HOSTED_FRONTEND_URL}/*`] };
  session.defaultSession.webRequest.onBeforeRequest(filter, (details, callback) => {
    const rewritten = details.url.replace(HOSTED_FRONTEND_URL, `http://localhost:${getServerPort()}`);
    callback({ redirectURL: rewritten });
  });

  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
    console.error(`Failed to load ${validatedURL}: ${errorDescription} (${errorCode})`);
    if (errorCode === -3) return;
    showErrorDialog('Page failed to load', new Error(`${errorDescription} (${errorCode})\n${validatedURL}`));
  });

  // Auto-sync active search space from URL navigation
  const syncSearchSpace = (url: string) => {
    const match = url.match(/\/dashboard\/(\d+)/);
    if (match) {
      setActiveSearchSpaceId(match[1]);
    }
  };
  mainWindow.webContents.on('did-navigate', (_event, url) => syncSearchSpace(url));
  mainWindow.webContents.on('did-navigate-in-page', (_event, url) => syncSearchSpace(url));

  if (isDev) {
    mainWindow.webContents.openDevTools();
  }

  // Hide-to-tray on close (don't actually destroy the window unless the
  // user really is quitting). Applies to every instance — including the one
  // created lazily after a launch-at-login boot.
  mainWindow.on('close', (e) => {
    if (!isQuitting && mainWindow) {
      e.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  return mainWindow;
}

export function showMainWindow(source: 'tray_click' | 'tray_menu' | 'shortcut' = 'tray_click'): void {
  const existing = getMainWindow();
  const reopened = !existing || existing.isDestroyed();
  if (reopened) {
    createMainWindow('/dashboard');
  } else {
    existing.show();
    existing.focus();
  }
  trackEvent('desktop_main_window_shown', { source, reopened });
}
