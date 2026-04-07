import { BrowserWindow, clipboard, globalShortcut, ipcMain, screen, shell } from 'electron';
import path from 'path';
import { IPC_CHANNELS } from '../ipc/channels';
import { checkAccessibilityPermission, getFrontmostApp, simulateCopy, simulatePaste } from './platform';
import { getServerPort } from './server';
import { getShortcuts } from './shortcuts';
import { getActiveSearchSpaceId } from './active-search-space';

let currentShortcut = '';
let quickAskWindow: BrowserWindow | null = null;
let pendingText = '';
let pendingMode = '';
let pendingSearchSpaceId: string | null = null;
let sourceApp = '';
let savedClipboard = '';

function destroyQuickAsk(): void {
  if (quickAskWindow && !quickAskWindow.isDestroyed()) {
    quickAskWindow.close();
  }
  quickAskWindow = null;
  pendingMode = '';
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
    height: 750,
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

  const spaceId = pendingSearchSpaceId;
  const route = spaceId ? `/dashboard/${spaceId}/new-chat` : '/dashboard';
  quickAskWindow.loadURL(`http://localhost:${getServerPort()}${route}?quickAssist=true`);

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

async function openQuickAsk(text: string): Promise<void> {
  pendingText = text;
  pendingMode = 'quick-assist';
  pendingSearchSpaceId = await getActiveSearchSpaceId();
  const cursor = screen.getCursorScreenPoint();
  const pos = clampToScreen(cursor.x, cursor.y, 450, 750);
  createQuickAskWindow(pos.x, pos.y);
}

async function quickAskHandler(): Promise<void> {
  console.log('[quick-ask] Handler triggered');

  if (quickAskWindow && !quickAskWindow.isDestroyed()) {
    console.log('[quick-ask] Window already open, closing');
    destroyQuickAsk();
    return;
  }

  if (!checkAccessibilityPermission()) {
    console.log('[quick-ask] Accessibility permission denied');
    return;
  }

  savedClipboard = clipboard.readText();
  console.log('[quick-ask] Saved clipboard length:', savedClipboard.length);

  const copyOk = simulateCopy();
  console.log('[quick-ask] simulateCopy result:', copyOk);

  await new Promise((r) => setTimeout(r, 300));

  const afterCopy = clipboard.readText();
  const selected = afterCopy.trim();
  console.log('[quick-ask] Clipboard after copy length:', afterCopy.length, 'changed:', afterCopy !== savedClipboard);

  const text = selected || savedClipboard.trim();

  sourceApp = getFrontmostApp();
  console.log('[quick-ask] Source app:', sourceApp, '| Opening Quick Assist with', text.length, 'chars', selected ? '(selected)' : text ? '(clipboard fallback)' : '(empty)');
  openQuickAsk(text);
}

let ipcRegistered = false;

function registerIpcHandlers(): void {
  if (ipcRegistered) return;
  ipcRegistered = true;

  ipcMain.handle(IPC_CHANNELS.QUICK_ASK_TEXT, () => {
    const text = pendingText;
    pendingText = '';
    return text;
  });

  ipcMain.handle(IPC_CHANNELS.SET_QUICK_ASK_MODE, (_event, mode: string) => {
    pendingMode = mode;
  });

  ipcMain.handle(IPC_CHANNELS.GET_QUICK_ASK_MODE, (event) => {
    if (quickAskWindow && !quickAskWindow.isDestroyed() && event.sender.id === quickAskWindow.webContents.id) {
      return pendingMode;
    }
    return '';
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

async function registerShortcut(): Promise<void> {
  const shortcuts = await getShortcuts();
  currentShortcut = shortcuts.quickAsk;

  const ok = globalShortcut.register(currentShortcut, () => { quickAskHandler(); });
  console.log(`[quick-ask] Register ${currentShortcut}: ${ok ? 'OK' : 'FAILED'}`);
}

export async function registerQuickAsk(): Promise<void> {
  registerIpcHandlers();
  await registerShortcut();
}

export function unregisterQuickAsk(): void {
  if (currentShortcut) globalShortcut.unregister(currentShortcut);
}

export async function reregisterQuickAsk(): Promise<void> {
  unregisterQuickAsk();
  await registerShortcut();
}
