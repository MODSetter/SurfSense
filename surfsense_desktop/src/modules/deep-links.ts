import { app } from 'electron';
import path from 'path';
import { getMainWindow } from './window';
import { getServerPort } from './server';
import { trackEvent } from './analytics';

const PROTOCOL = 'surfsense';

let deepLinkUrl: string | null = null;

function handleDeepLink(url: string) {
  if (!url.startsWith(`${PROTOCOL}://`)) return;

  deepLinkUrl = url;

  const win = getMainWindow();
  if (!win) return;

  const parsed = new URL(url);
  trackEvent('desktop_deep_link_received', {
    host: parsed.hostname,
    path: parsed.pathname,
  });
  if (parsed.hostname === 'auth' && parsed.pathname === '/callback') {
    const params = parsed.searchParams.toString();
    win.loadURL(`http://localhost:${getServerPort()}/auth/callback?${params}`);
  }

  win.show();
  win.focus();
}

export function setupDeepLinks(): boolean {
  const gotTheLock = app.requestSingleInstanceLock();
  if (!gotTheLock) {
    return false;
  }

  app.on('second-instance', (_event, argv) => {
    const url = argv.find((arg) => arg.startsWith(`${PROTOCOL}://`));
    if (url) handleDeepLink(url);

    const win = getMainWindow();
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });

  app.on('open-url', (event, url) => {
    event.preventDefault();
    handleDeepLink(url);
  });

  if (process.defaultApp) {
    if (process.argv.length >= 2) {
      app.setAsDefaultProtocolClient(PROTOCOL, process.execPath, [path.resolve(process.argv[1])]);
    }
  } else {
    app.setAsDefaultProtocolClient(PROTOCOL);
  }

  return true;
}

export function handlePendingDeepLink(): void {
  if (deepLinkUrl) {
    handleDeepLink(deepLinkUrl);
    deepLinkUrl = null;
  }
}

// True when a deep link arrived before the main window existed. Callers can
// use this to force-create a window even on a "started hidden" boot, so we
// don't silently swallow a `surfsense://` URL the user actually clicked on.
export function hasPendingDeepLink(): boolean {
  return deepLinkUrl !== null;
}
