import { app, BrowserWindow, shell, session } from 'electron';
import path from 'path';
import { showErrorDialog } from './errors';
import { getServerPort } from './server';

const isDev = !app.isPackaged;
const HOSTED_FRONTEND_URL = process.env.HOSTED_FRONTEND_URL as string;

let mainWindow: BrowserWindow | null = null;

export function getMainWindow(): BrowserWindow | null {
  return mainWindow;
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

  if (isDev) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  return mainWindow;
}
