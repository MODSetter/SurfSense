import { app, BrowserWindow, shell, session } from 'electron';
import path from 'path';
import { trackEvent } from './analytics';
import { showErrorDialog } from './errors';
import { getServerOrigin, getServerPort } from './server';
import { setActiveSearchSpaceId } from './active-search-space';

const isDev = !app.isPackaged;
const isMac = process.platform === 'darwin';
const WINDOW_TITLE = 'SurfSense';

function getHostedFrontendUrl(): string {
  return (
    process.env.SURFSENSE_HOSTED_FRONTEND_URL_OVERRIDE ||
    process.env.HOSTED_FRONTEND_URL ||
    'https://surfsense.com'
  );
}

function getHostedFrontendHosts(): string[] {
  try {
    const host = new URL(getHostedFrontendUrl()).host;
    const sibling = host.startsWith('www.') ? host.slice(4) : `www.${host}`;
    return Array.from(new Set([host, sibling]));
  } catch {
    return [];
  }
}

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
    title: WINDOW_TITLE,
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
    ...(isMac
      ? {
          titleBarStyle: 'hidden' as const,
          trafficLightPosition: { x: 12, y: 10 },
        }
      : {}),
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  mainWindow.webContents.on('page-title-updated', (event) => {
    event.preventDefault();
    mainWindow?.setTitle(WINDOW_TITLE);
  });
  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow?.setTitle(WINDOW_TITLE);
  });

  mainWindow.loadURL(`${getServerOrigin()}${initialPath}`);

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith(getServerOrigin())) {
      return { action: 'allow' };
    }
    shell.openExternal(url);
    return { action: 'deny' };
  });

  const hostedHosts = getHostedFrontendHosts();
  const rewriteFilter = {
    urls: hostedHosts.flatMap((h) => [`http://${h}/*`, `https://${h}/*`]),
  };
  if (rewriteFilter.urls.length > 0) {
    session.defaultSession.webRequest.onBeforeRequest(rewriteFilter, (details, callback) => {
      try {
        const u = new URL(details.url);
        const originalHost = u.host;
        const local = new URL(getServerOrigin());
        u.protocol = local.protocol;
        u.host = local.host;
        trackEvent('desktop_oauth_redirect_intercepted', {
          host: originalHost,
          path: u.pathname,
          rewritten_to_port: getServerPort(),
        });
        callback({ redirectURL: u.toString() });
      } catch {
        callback({});
      }
    });
  }

  // Diagnostic: connector callback landing somewhere other than localhost
  // means the rewrite missed and the user is stranded off-app.
  session.defaultSession.webRequest.onCompleted(
    { urls: ['*://*/dashboard/*/connectors/callback*'] },
    (details) => {
      try {
        const u = new URL(details.url);
        if (u.hostname === 'localhost' || u.hostname === '127.0.0.1') return;
        trackEvent('desktop_oauth_redirect_missed', {
          host: u.host,
          path: u.pathname,
          status_code: details.statusCode,
        });
      } catch {
        // ignore malformed URLs
      }
    }
  );

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
