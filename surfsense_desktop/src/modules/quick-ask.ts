import { BrowserWindow, clipboard, globalShortcut, ipcMain, screen } from 'electron';
import path from 'path';
import { IPC_CHANNELS } from '../ipc/channels';
import { getServerPort } from './server';

const SHORTCUT = 'CommandOrControl+Option+S';
let quickAskWindow: BrowserWindow | null = null;
let pendingText = '';

function hideQuickAsk(): void {
  if (quickAskWindow && !quickAskWindow.isDestroyed()) {
    quickAskWindow.hide();
  }
}

function createQuickAskWindow(x: number, y: number): BrowserWindow {
  if (quickAskWindow && !quickAskWindow.isDestroyed()) {
    quickAskWindow.setPosition(x, y);
    quickAskWindow.show();
    quickAskWindow.focus();
    return quickAskWindow;
  }

  quickAskWindow = new BrowserWindow({
    width: 450,
    height: 550,
    x,
    y,
    type: 'panel',
    resizable: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
    show: false,
    skipTaskbar: true,
  });

  quickAskWindow.loadURL(`http://localhost:${getServerPort()}/dashboard`);

  quickAskWindow.once('ready-to-show', () => {
    quickAskWindow?.show();
  });

  quickAskWindow.on('blur', hideQuickAsk);

  quickAskWindow.on('closed', () => {
    quickAskWindow = null;
  });

  return quickAskWindow;
}

export function registerQuickAsk(): void {
  const ok = globalShortcut.register(SHORTCUT, () => {
    if (quickAskWindow && !quickAskWindow.isDestroyed() && quickAskWindow.isVisible()) {
      hideQuickAsk();
      return;
    }

    const text = clipboard.readText().trim();
    if (!text) return;

    pendingText = text;
    const cursor = screen.getCursorScreenPoint();
    createQuickAskWindow(cursor.x, cursor.y);
  });

  if (!ok) {
    console.log(`Quick-ask: failed to register ${SHORTCUT}`);
  }

  ipcMain.handle(IPC_CHANNELS.QUICK_ASK_TEXT, () => {
    const text = pendingText;
    pendingText = '';
    return text;
  });
}

export function unregisterQuickAsk(): void {
  globalShortcut.unregister(SHORTCUT);
}
