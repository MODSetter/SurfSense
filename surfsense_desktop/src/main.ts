import { app, BrowserWindow, shell, ipcMain, session, dialog, clipboard } from 'electron';
import path from 'path';
import { getPort } from 'get-port-please';

function showErrorDialog(title: string, error: unknown): void {
  const err = error instanceof Error ? error : new Error(String(error));
  console.error(`${title}:`, err);

  if (app.isReady()) {
    const detail = err.stack || err.message;
    const buttonIndex = dialog.showMessageBoxSync({
      type: 'error',
      buttons: ['OK', process.platform === 'darwin' ? 'Copy Error' : 'Copy error'],
      defaultId: 0,
      noLink: true,
      message: title,
      detail,
    });
    if (buttonIndex === 1) {
      clipboard.writeText(`${title}\n${detail}`);
    }
  } else {
    dialog.showErrorBox(title, err.stack || err.message);
  }
}

process.on('uncaughtException', (error) => {
  showErrorDialog('Unhandled Error', error);
});

process.on('unhandledRejection', (reason) => {
  showErrorDialog('Unhandled Promise Rejection', reason);
});

const isDev = !app.isPackaged;
let mainWindow: BrowserWindow | null = null;
let deepLinkUrl: string | null = null;
let serverPort: number = 3000; // overwritten at startup with a free port

const PROTOCOL = 'surfsense';
// Injected at compile time from .env.desktop via esbuild define
const HOSTED_FRONTEND_URL = process.env.HOSTED_FRONTEND_URL as string;

function getStandalonePath(): string {
  if (isDev) {
    return path.join(__dirname, '..', '..', 'surfsense_web', '.next', 'standalone', 'surfsense_web');
  }
  return path.join(process.resourcesPath, 'standalone');
}

async function waitForServer(url: string, maxRetries = 60): Promise<boolean> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(url);
      if (res.ok || res.status === 404 || res.status === 500) return true;
    } catch {
      // not ready yet
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

async function startNextServer(): Promise<void> {
  if (isDev) return;

  serverPort = await getPort({ port: 3000, portRange: [30_011, 50_000] });
  console.log(`Selected port ${serverPort}`);

  const standalonePath = getStandalonePath();
  const serverScript = path.join(standalonePath, 'server.js');

  // The standalone server.js reads PORT / HOSTNAME from process.env and
  // uses process.chdir(__dirname). Running it via require() in the same
  // process is the proven approach (avoids spawning a second Electron
  // instance whose ASAR-patched fs breaks Next.js static file serving).
  process.env.PORT = String(serverPort);
  process.env.HOSTNAME = 'localhost';
  process.env.NODE_ENV = 'production';
  process.chdir(standalonePath);

  require(serverScript);

  const ready = await waitForServer(`http://localhost:${serverPort}`);
  if (!ready) {
    throw new Error('Next.js server failed to start within 30 s');
  }
  console.log(`Next.js server ready on port ${serverPort}`);
}

function createWindow() {
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

  mainWindow.loadURL(`http://localhost:${serverPort}/login`);

  // External links open in system browser, not in the Electron window
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://localhost')) {
      return { action: 'allow' };
    }
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Intercept backend OAuth redirects targeting the hosted web frontend
  // and rewrite them to localhost so the user stays in the desktop app.
  const filter = { urls: [`${HOSTED_FRONTEND_URL}/*`] };
  session.defaultSession.webRequest.onBeforeRequest(filter, (details, callback) => {
    const rewritten = details.url.replace(HOSTED_FRONTEND_URL, `http://localhost:${serverPort}`);
    callback({ redirectURL: rewritten });
  });

  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
    console.error(`Failed to load ${validatedURL}: ${errorDescription} (${errorCode})`);
    if (errorCode === -3) return; // ERR_ABORTED — normal during redirects
    showErrorDialog('Page failed to load', new Error(`${errorDescription} (${errorCode})\n${validatedURL}`));
  });

  if (isDev) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC handlers
ipcMain.on('open-external', (_event, url: string) => {
  shell.openExternal(url);
});

ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});

// Deep link handling
function handleDeepLink(url: string) {
  if (!url.startsWith(`${PROTOCOL}://`)) return;

  deepLinkUrl = url;

  if (!mainWindow) return;

  // Rewrite surfsense:// deep link to localhost so TokenHandler.tsx processes it
  const parsed = new URL(url);
  if (parsed.hostname === 'auth' && parsed.pathname === '/callback') {
    const params = parsed.searchParams.toString();
    mainWindow.loadURL(`http://localhost:${serverPort}/auth/callback?${params}`);
  }

  mainWindow.show();
  mainWindow.focus();
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

    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
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

// App lifecycle
app.whenReady().then(async () => {
  try {
    await startNextServer();
  } catch (error) {
    showErrorDialog('Failed to start SurfSense', error);
    setTimeout(() => app.quit(), 0);
    return;
  }
  createWindow();

  // If a deep link was received before the window was ready, handle it now
  if (deepLinkUrl) {
    handleDeepLink(deepLinkUrl);
    deepLinkUrl = null;
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
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
