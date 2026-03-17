import { app, BrowserWindow, shell, ipcMain } from 'electron';
import path from 'path';
import { spawn, ChildProcess } from 'child_process';
import { resolveEnv } from './resolve-env';

const isDev = !app.isPackaged;
let mainWindow: BrowserWindow | null = null;
let serverProcess: ChildProcess | null = null;

const SERVER_PORT = 3000;

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

// App lifecycle
app.whenReady().then(async () => {
  await startNextServer();
  createWindow();

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
