import { clipboard, globalShortcut, ipcMain, screen } from 'electron';
import { IPC_CHANNELS } from '../../ipc/channels';
import { getFrontmostApp, hasAccessibilityPermission, simulatePaste } from '../platform';
import { getMainWindow } from '../window';
import { createSuggestionWindow, destroySuggestion, getSuggestionWindow } from './suggestion-window';

let autocompleteEnabled = true;
let savedClipboard = '';
let sourceApp = '';
let pendingSuggestionText = '';

function isSurfSenseWindow(): boolean {
  const app = getFrontmostApp();
  return app === 'Electron' || app === 'SurfSense' || app === 'surfsense-desktop';
}

async function triggerAutocomplete(): Promise<void> {
  if (!hasAccessibilityPermission()) return;
  if (isSurfSenseWindow()) return;

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
          text: '',
          cursorPosition: 0,
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
      destroySuggestion();
    }
  });
  ipcMain.handle(IPC_CHANNELS.GET_AUTOCOMPLETE_ENABLED, () => autocompleteEnabled);
}

export function registerAutocomplete(): void {
  registerIpcHandlers();

  // TODO: Phase 2 — replace with vision-based trigger (desktopCapturer + globalShortcut)
  console.log('[autocomplete] IPC handlers registered');
}

export function unregisterAutocomplete(): void {
  destroySuggestion();
}
