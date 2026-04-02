import { BrowserWindow, clipboard, ipcMain, screen, shell } from 'electron';
import path from 'path';
import { IPC_CHANNELS } from '../ipc/channels';
import { allPermissionsGranted } from './permissions';
import { getFieldContent, getFrontmostApp, hasAccessibilityPermission, simulatePaste } from './platform';
import { getServerPort } from './server';
import { getMainWindow } from './window';

const DEBOUNCE_MS = 600;
const TOOLTIP_WIDTH = 420;
const TOOLTIP_HEIGHT = 140;

let uIOhook: any = null;
let UiohookKey: any = {};
let IGNORED_KEYCODES: Set<number> = new Set();

let suggestionWindow: BrowserWindow | null = null;
let debounceTimer: ReturnType<typeof setTimeout> | null = null;
let hookStarted = false;
let autocompleteEnabled = true;
let savedClipboard = '';
let sourceApp = '';
let pendingSuggestionText = '';

function loadUiohook(): boolean {
  if (uIOhook) return true;
  try {
    const mod = require('uiohook-napi');
    uIOhook = mod.uIOhook;
    UiohookKey = mod.UiohookKey;
    IGNORED_KEYCODES = new Set([
      UiohookKey.Shift, UiohookKey.ShiftRight,
      UiohookKey.Ctrl, UiohookKey.CtrlRight,
      UiohookKey.Alt, UiohookKey.AltRight,
      UiohookKey.Meta, UiohookKey.MetaRight,
      UiohookKey.CapsLock, UiohookKey.NumLock, UiohookKey.ScrollLock,
      UiohookKey.F1, UiohookKey.F2, UiohookKey.F3, UiohookKey.F4,
      UiohookKey.F5, UiohookKey.F6, UiohookKey.F7, UiohookKey.F8,
      UiohookKey.F9, UiohookKey.F10, UiohookKey.F11, UiohookKey.F12,
      UiohookKey.PrintScreen,
      UiohookKey.Insert, UiohookKey.Delete,
      UiohookKey.Home, UiohookKey.End,
      UiohookKey.PageUp, UiohookKey.PageDown,
      UiohookKey.ArrowUp, UiohookKey.ArrowDown,
      UiohookKey.ArrowLeft, UiohookKey.ArrowRight,
    ]);
    console.log('[autocomplete] uiohook-napi loaded');
    return true;
  } catch (err) {
    console.error('[autocomplete] Failed to load uiohook-napi:', err);
    return false;
  }
}

function destroySuggestion(): void {
  if (suggestionWindow && !suggestionWindow.isDestroyed()) {
    suggestionWindow.close();
  }
  suggestionWindow = null;
}

function clampToScreen(x: number, y: number, w: number, h: number): { x: number; y: number } {
  const display = screen.getDisplayNearestPoint({ x, y });
  const { x: dx, y: dy, width: dw, height: dh } = display.workArea;
  return {
    x: Math.max(dx, Math.min(x, dx + dw - w)),
    y: Math.max(dy, Math.min(y, dy + dh - h)),
  };
}

function createSuggestionWindow(x: number, y: number): BrowserWindow {
  destroySuggestion();

  const pos = clampToScreen(x, y + 20, TOOLTIP_WIDTH, TOOLTIP_HEIGHT);

  suggestionWindow = new BrowserWindow({
    width: TOOLTIP_WIDTH,
    height: TOOLTIP_HEIGHT,
    x: pos.x,
    y: pos.y,
    frame: false,
    transparent: true,
    focusable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    hasShadow: true,
    type: 'panel',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
    show: false,
  });

  suggestionWindow.loadURL(`http://localhost:${getServerPort()}/desktop/suggestion?t=${Date.now()}`);

  suggestionWindow.once('ready-to-show', () => {
    suggestionWindow?.showInactive();
  });

  suggestionWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://localhost')) {
      return { action: 'allow' };
    }
    shell.openExternal(url);
    return { action: 'deny' };
  });

  suggestionWindow.on('closed', () => {
    suggestionWindow = null;
  });

  return suggestionWindow;
}

function clearDebounce(): void {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }
}

function isSurfSenseWindow(): boolean {
  const app = getFrontmostApp();
  return app === 'Electron' || app === 'SurfSense' || app === 'surfsense-desktop';
}

function onKeyDown(event: { keycode: number; ctrlKey?: boolean; metaKey?: boolean; altKey?: boolean }): void {
  if (!autocompleteEnabled) return;

  if (event.keycode === UiohookKey.Tab && suggestionWindow && !suggestionWindow.isDestroyed()) {
    if (pendingSuggestionText) {
      acceptAndInject(pendingSuggestionText);
    }
    return;
  }

  if (event.keycode === UiohookKey.Escape) {
    if (suggestionWindow && !suggestionWindow.isDestroyed()) {
      destroySuggestion();
      pendingSuggestionText = '';
    }
    clearDebounce();
    return;
  }

  if (IGNORED_KEYCODES.has(event.keycode)) return;
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  if (isSurfSenseWindow()) return;

  if (suggestionWindow && !suggestionWindow.isDestroyed()) {
    destroySuggestion();
  }

  clearDebounce();
  debounceTimer = setTimeout(() => {
    triggerAutocomplete();
  }, DEBOUNCE_MS);
}

async function triggerAutocomplete(): Promise<void> {
  if (!hasAccessibilityPermission()) return;
  if (isSurfSenseWindow()) return;

  const fieldContent = getFieldContent();
  if (!fieldContent || !fieldContent.text.trim()) return;
  if (fieldContent.text.trim().length < 5) return;

  sourceApp = getFrontmostApp();
  savedClipboard = clipboard.readText();

  const cursor = screen.getCursorScreenPoint();
  const win = createSuggestionWindow(cursor.x, cursor.y);

  let searchSpaceId = '1';
  const mainWin = getMainWindow();
  if (mainWin && !mainWin.isDestroyed()) {
    const mainUrl = mainWin.webContents.getURL();
    const match = mainUrl.match(/\/dashboard\/(\d+)/);
    if (match) {
      searchSpaceId = match[1];
    }
  }

  win.webContents.once('did-finish-load', () => {
    if (suggestionWindow && !suggestionWindow.isDestroyed()) {
      suggestionWindow.webContents.send(IPC_CHANNELS.AUTOCOMPLETE_CONTEXT, {
        text: fieldContent.text,
        cursorPosition: fieldContent.cursorPosition,
        searchSpaceId,
      });
    }
  });
}

async function acceptAndInject(text: string): Promise<void> {
  if (!sourceApp) return;
  if (!hasAccessibilityPermission()) return;

  clipboard.writeText(text);
  destroySuggestion();
  pendingSuggestionText = '';

  try {
    await new Promise((r) => setTimeout(r, 50));
    simulatePaste();
    await new Promise((r) => setTimeout(r, 100));
    clipboard.writeText(savedClipboard);
  } catch {
    clipboard.writeText(savedClipboard);
  }
}

function registerIpcHandlers(): void {
  ipcMain.handle(IPC_CHANNELS.ACCEPT_SUGGESTION, async (_event, text: string) => {
    await acceptAndInject(text);
  });
  ipcMain.handle(IPC_CHANNELS.DISMISS_SUGGESTION, () => {
    destroySuggestion();
    pendingSuggestionText = '';
  });
  ipcMain.handle(IPC_CHANNELS.UPDATE_SUGGESTION_TEXT, (_event, text: string) => {
    pendingSuggestionText = text;
  });
  ipcMain.handle(IPC_CHANNELS.SET_AUTOCOMPLETE_ENABLED, (_event, enabled: boolean) => {
    autocompleteEnabled = enabled;
    if (!enabled) {
      clearDebounce();
      destroySuggestion();
    }
  });
  ipcMain.handle(IPC_CHANNELS.GET_AUTOCOMPLETE_ENABLED, () => autocompleteEnabled);
}

export function registerAutocomplete(): void {
  registerIpcHandlers();

  if (!allPermissionsGranted()) {
    console.log('[autocomplete] Permissions not granted — hook not started');
    return;
  }

  if (!loadUiohook()) {
    console.error('[autocomplete] Cannot start: uiohook-napi failed to load');
    return;
  }

  uIOhook.on('keydown', onKeyDown);
  try {
    uIOhook.start();
    hookStarted = true;
    console.log('[autocomplete] uIOhook started');
  } catch (err) {
    console.error('[autocomplete] uIOhook.start() failed:', err);
  }
}

export function unregisterAutocomplete(): void {
  clearDebounce();
  destroySuggestion();
  if (uIOhook && hookStarted) {
    try { uIOhook.stop(); } catch { /* already stopped */ }
  }
}
