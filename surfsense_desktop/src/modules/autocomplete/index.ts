import { clipboard, globalShortcut, ipcMain, screen } from 'electron';
import { IPC_CHANNELS } from '../../ipc/channels';
import { getFrontmostApp, hasAccessibilityPermission, simulatePaste } from '../platform';
import { hasScreenRecordingPermission, requestAccessibility, requestScreenRecording } from '../permissions';
import { getMainWindow } from '../window';
import { captureScreen } from './screenshot';
import { createSuggestionWindow, destroySuggestion, getSuggestionWindow } from './suggestion-window';

const SHORTCUT = 'CommandOrControl+Shift+Space';

let autocompleteEnabled = true;
let savedClipboard = '';
let sourceApp = '';

function isSurfSenseWindow(): boolean {
  const app = getFrontmostApp();
  return app === 'Electron' || app === 'SurfSense' || app === 'surfsense-desktop';
}

async function triggerAutocomplete(): Promise<void> {
  if (!autocompleteEnabled) return;
  if (isSurfSenseWindow()) return;

  if (!hasScreenRecordingPermission()) {
    requestScreenRecording();
    return;
  }

  sourceApp = getFrontmostApp();
  savedClipboard = clipboard.readText();

  const screenshot = await captureScreen();
  if (!screenshot) {
    console.error('[autocomplete] Screenshot capture failed');
    return;
  }

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
          screenshot,
          searchSpaceId,
        });
      }
    }, 300);
  });
}

async function acceptAndInject(text: string): Promise<void> {
  if (!sourceApp) return;

  if (!hasAccessibilityPermission()) {
    requestAccessibility();
    return;
  }

  clipboard.writeText(text);
  destroySuggestion();

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

  const ok = globalShortcut.register(SHORTCUT, () => {
    const sw = getSuggestionWindow();
    if (sw && !sw.isDestroyed()) {
      destroySuggestion();
      return;
    }
    triggerAutocomplete();
  });

  if (!ok) {
    console.error(`[autocomplete] Failed to register shortcut ${SHORTCUT}`);
  } else {
    console.log(`[autocomplete] Registered shortcut ${SHORTCUT}`);
  }
}

export function unregisterAutocomplete(): void {
  globalShortcut.unregister(SHORTCUT);
  destroySuggestion();
}
