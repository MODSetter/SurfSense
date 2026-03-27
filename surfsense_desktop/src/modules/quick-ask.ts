import { BrowserWindow, clipboard, globalShortcut, ipcMain, screen, shell } from 'electron';
import path from 'path';
import { IPC_CHANNELS } from '../ipc/channels';
import { checkAccessibilityPermission, getFrontmostApp, simulatePaste } from './platform';
import { getServerPort } from './server';

const SHORTCUT = 'CommandOrControl+Option+S';
let quickAskWindow: BrowserWindow | null = null;
let pendingText = '';
let sourceApp = '';
let savedClipboard = '';

function destroyQuickAsk(): void {
  if (quickAskWindow && !quickAskWindow.isDestroyed()) {
    quickAskWindow.close();
  }
  quickAskWindow = null;
}

function clampToScreen(x: number, y: number, w: number, h: number): { x: number; y: number } {
  const display = screen.getDisplayNearestPoint({ x, y });
  const { x: dx, y: dy, width: dw, height: dh } = display.workArea;
  return {
    x: Math.max(dx, Math.min(x, dx + dw - w)),
    y: Math.max(dy, Math.min(y, dy + dh - h)),
  };
}

function createQuickAskWindow(x: number, y: number): BrowserWindow {
  destroyQuickAsk();

  quickAskWindow = new BrowserWindow({
    width: 450,
    height: 550,
    x,
    y,
    ...(process.platform === 'darwin'
      ? { type: 'panel' as const }
      : { type: 'toolbar' as const, alwaysOnTop: true }),
    resizable: true,
    fullscreenable: false,
    maximizable: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
    show: false,
    skipTaskbar: true,
  });

  quickAskWindow.loadURL(`http://localhost:${getServerPort()}/dashboard/quick-ask`);

  quickAskWindow.once('ready-to-show', () => {
    quickAskWindow?.show();
  });

  quickAskWindow.webContents.on('before-input-event', (_event, input) => {
    if (input.key === 'Escape') destroyQuickAsk();
  });

  quickAskWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://localhost')) {
      return { action: 'allow' };
    }
    shell.openExternal(url);
    return { action: 'deny' };
  });

  quickAskWindow.on('closed', () => {
    quickAskWindow = null;
  });

  return quickAskWindow;
}

export function registerQuickAsk(): void {
  const ok = globalShortcut.register(SHORTCUT, () => {
    if (quickAskWindow && !quickAskWindow.isDestroyed()) {
      destroyQuickAsk();
      return;
    }

    sourceApp = getFrontmostApp();
    savedClipboard = clipboard.readText();

    const text = savedClipboard.trim();
    if (!text) return;

    pendingText = text;
    const cursor = screen.getCursorScreenPoint();
    const pos = clampToScreen(cursor.x, cursor.y, 450, 550);
    createQuickAskWindow(pos.x, pos.y);
  });

  if (!ok) {
    console.log(`Quick-ask: failed to register ${SHORTCUT}`);
  }

  ipcMain.handle(IPC_CHANNELS.QUICK_ASK_TEXT, () => {
    return pendingText;
  });

  ipcMain.handle(IPC_CHANNELS.REPLACE_TEXT, async (_event, text: string) => {
    if (!sourceApp) return;

    if (!checkAccessibilityPermission()) return;

    clipboard.writeText(text);
    destroyQuickAsk();

    try {
      await new Promise((r) => setTimeout(r, 50));
      simulatePaste();
      await new Promise((r) => setTimeout(r, 100));
      clipboard.writeText(savedClipboard);
    } catch {
      clipboard.writeText(savedClipboard);
    }
  });
}

export function unregisterQuickAsk(): void {
  globalShortcut.unregister(SHORTCUT);
}
