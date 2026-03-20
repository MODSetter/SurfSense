import { app, BrowserWindow, clipboard, Menu, Tray } from 'electron';
import path from 'path';
import { getServerPort } from './server';
import { setClipboardContent } from './clipboard';

let tray: Tray | null = null;
let clipWindow: BrowserWindow | null = null;

function getIconPath(): string {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'icon.png');
  }
  return path.join(__dirname, '..', 'assets', 'icon.png');
}

function createClipWindow(): BrowserWindow {
  if (clipWindow && !clipWindow.isDestroyed()) {
    clipWindow.focus();
    return clipWindow;
  }

  clipWindow = new BrowserWindow({
    width: 420,
    height: 620,
    resizable: true,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
    show: false,
    titleBarStyle: 'hiddenInset',
  });

  clipWindow.loadURL(`http://localhost:${getServerPort()}/dashboard`);

  clipWindow.once('ready-to-show', () => {
    clipWindow?.show();
  });

  clipWindow.on('closed', () => {
    clipWindow = null;
  });

  return clipWindow;
}

export function setupTray(): void {
  tray = new Tray(getIconPath());
  tray.setToolTip('SurfSense');

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Ask about clipboard',
      click: () => {
        const text = clipboard.readText();
        setClipboardContent(text);
        createClipWindow();
      },
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => app.quit(),
    },
  ]);

  tray.setContextMenu(contextMenu);
}
