import { clipboard, ipcMain, screen } from 'electron';
import { IPC_CHANNELS } from '../../ipc/channels';
import { getFrontmostApp, hasAccessibilityPermission, simulatePaste } from '../platform';
import { getMainWindow } from '../window';
import {
  appendToBuffer, buildKeycodeMap, getBuffer, getBufferTrimmed,
  getLastTrackedApp, removeLastChar, resetBuffer, resolveChar, setLastTrackedApp,
} from './keystroke-buffer';
import { createSuggestionWindow, destroySuggestion, getSuggestionWindow } from './suggestion-window';

const DEBOUNCE_MS = 600;

let uIOhook: any = null;
let UiohookKey: any = {};
let IGNORED_KEYCODES: Set<number> = new Set();

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
    ]);
    buildKeycodeMap();
    console.log('[autocomplete] uiohook-napi loaded');
    return true;
  } catch (err) {
    console.error('[autocomplete] Failed to load uiohook-napi:', err);
    return false;
  }
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

function onKeyDown(event: {
  keycode: number;
  shiftKey?: boolean;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
}): void {
  if (!autocompleteEnabled) return;

  const currentApp = getFrontmostApp();
  if (currentApp !== getLastTrackedApp()) {
    resetBuffer();
    setLastTrackedApp(currentApp);
  }

  const win = getSuggestionWindow();

  if (event.keycode === UiohookKey.Tab && win && !win.isDestroyed()) {
    if (pendingSuggestionText) {
      acceptAndInject(pendingSuggestionText);
    }
    return;
  }

  if (event.keycode === UiohookKey.Escape) {
    if (win && !win.isDestroyed()) {
      destroySuggestion();
      pendingSuggestionText = '';
    }
    clearDebounce();
    return;
  }

  if (currentApp === 'Electron' || currentApp === 'SurfSense' || currentApp === 'surfsense-desktop') {
    return;
  }

  if (event.ctrlKey || event.metaKey || event.altKey) {
    resetBuffer();
    clearDebounce();
    return;
  }

  if (event.keycode === UiohookKey.Backspace) {
    removeLastChar();
  } else if (event.keycode === UiohookKey.Delete) {
    // forward delete doesn't affect our trailing buffer
  } else if (event.keycode === UiohookKey.Enter) {
    appendToBuffer('\n');
  } else if (event.keycode === UiohookKey.Space) {
    appendToBuffer(' ');
  } else if (
    event.keycode === UiohookKey.ArrowLeft || event.keycode === UiohookKey.ArrowRight ||
    event.keycode === UiohookKey.ArrowUp || event.keycode === UiohookKey.ArrowDown ||
    event.keycode === UiohookKey.Home || event.keycode === UiohookKey.End ||
    event.keycode === UiohookKey.PageUp || event.keycode === UiohookKey.PageDown
  ) {
    resetBuffer();
    clearDebounce();
    return;
  } else if (IGNORED_KEYCODES.has(event.keycode)) {
    return;
  } else {
    const ch = resolveChar(event.keycode, !!event.shiftKey);
    if (ch) appendToBuffer(ch);
  }

  if (win && !win.isDestroyed()) {
    destroySuggestion();
  }

  clearDebounce();
  debounceTimer = setTimeout(() => {
    triggerAutocomplete();
  }, DEBOUNCE_MS);
}

function onMouseClick(): void {
  resetBuffer();
}

async function triggerAutocomplete(): Promise<void> {
  if (!hasAccessibilityPermission()) return;
  if (isSurfSenseWindow()) return;

  const text = getBufferTrimmed();
  if (!text || text.length < 5) return;

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
    const sw = getSuggestionWindow();
    setTimeout(() => {
      if (sw && !sw.isDestroyed()) {
        sw.webContents.send(IPC_CHANNELS.AUTOCOMPLETE_CONTEXT, {
          text: getBuffer(),
          cursorPosition: getBuffer().length,
          searchSpaceId,
        });
      }
    }, 300);
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
    appendToBuffer(text);
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

  if (!loadUiohook()) {
    console.error('[autocomplete] Cannot start: uiohook-napi failed to load');
    return;
  }

  uIOhook.on('keydown', onKeyDown);
  uIOhook.on('click', onMouseClick);
  try {
    uIOhook.start();
    hookStarted = true;
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
