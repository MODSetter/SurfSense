import { app, BrowserWindow, shell, ipcMain, session } from 'electron';
import path from 'path';
import { spawn, ChildProcess } from 'child_process';
import { resolveEnv } from './resolve-env';

const isDev = !app.isPackaged;
let mainWindow: BrowserWindow | null = null;
let serverProcess: ChildProcess | null = null;
let deepLinkUrl: string | null = null;

const SERVER_PORT = 3000;
const PROTOCOL = 'surfsense';
// TODO: Hardcoded URL is fragile — production domain may change and
// self-hosted users have their own. Two options:
//   1. Load from .env file using dotenv — users edit the file to change it.
//   2. Backend endpoint (GET /api/v1/config/frontend-url) that returns
//      the backend's NEXT_FRONTEND_URL — automatic, no file to manage.
const HOSTED_FRONTEND_URL = 'https://surfsense.net';

function getStandalonePath(): string {
  if (isDev) {
    return path.join(__dirname, '..', '..', 'surfsense_web', '.next', 'standalone');
  }
  return path.join(process.resourcesPath, 'standalone');
}

function startNextServer(): Promise<void> {
  return new Promise((resolve, reject) => {
    // In dev mode, Next.js dev server is already running externally
    if (isDev) {
      resolve();
      return;
    }

    const standalonePath = getStandalonePath();
    resolveEnv(standalonePath);
    const serverScript = path.join(standalonePath, 'server.js');

    serverProcess = spawn(process.execPath, [serverScript], {
      cwd: standalonePath,
      env: {
        ...process.env,
        PORT: String(SERVER_PORT),
        HOSTNAME: 'localhost',
        NODE_ENV: 'production',
      },
      stdio: 'pipe',
    });

    serverProcess.stdout?.on('data', (data: Buffer) => {
      const output = data.toString();
      console.log(`[next] ${output}`);
      if (output.includes('Ready') || output.includes('started server')) {
        resolve();
      }
    });

    serverProcess.stderr?.on('data', (data: Buffer) => {
      console.error(`[next] ${data.toString()}`);
    });

    serverProcess.on('error', reject);
    serverProcess.on('exit', (code) => {
      if (code !== 0 && code !== null) {
        reject(new Error(`Next.js server exited with code ${code}`));
      }
    });

    // Fallback: resolve after 5s even if we don't see the "Ready" message
    setTimeout(() => resolve(), 5000);
  });
}

function killServer() {
  if (serverProcess && !serverProcess.killed) {
    serverProcess.kill();
    serverProcess = null;
  }
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

  mainWindow.loadURL(`http://localhost:${SERVER_PORT}/login`);

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
    const rewritten = details.url.replace(HOSTED_FRONTEND_URL, `http://localhost:${SERVER_PORT}`);
    callback({ redirectURL: rewritten });
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
    mainWindow.loadURL(`http://localhost:${SERVER_PORT}/auth/callback?${params}`);
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
  await startNextServer();
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
  killServer();
});
