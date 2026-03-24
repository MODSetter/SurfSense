import { BrowserWindow, clipboard, globalShortcut, screen } from 'electron';
import path from 'path';
import { IPC_CHANNELS } from '../ipc/channels';
import { getServerPort } from './server';

const SHORTCUT = 'CommandOrControl+Option+S';
let quickAskWindow: BrowserWindow | null = null;

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
    alwaysOnTop: true,
    resizable: true,
    frame: false,
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

  quickAskWindow.on('closed', () => {
    quickAskWindow = null;
  });

  return quickAskWindow;
}

export function registerQuickAsk(): void {
  const ok = globalShortcut.register(SHORTCUT, () => {
    const text = clipboard.readText().trim();
    if (!text) return;

    const cursor = screen.getCursorScreenPoint();
    const win = createQuickAskWindow(cursor.x, cursor.y);

    win.webContents.send(IPC_CHANNELS.QUICK_ASK_TEXT, text);
  });

  if (!ok) {
    console.log(`Quick-ask: failed to register ${SHORTCUT}`);
  }
}

export function unregisterQuickAsk(): void {
  globalShortcut.unregister(SHORTCUT);
}
