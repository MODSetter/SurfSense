import { clipboard, globalShortcut, ipcMain, screen } from 'electron';
import { IPC_CHANNELS } from '../../ipc/channels';
import { getFrontmostApp, getWindowTitle, hasAccessibilityPermission, simulatePaste } from '../platform';
import { hasScreenRecordingPermission, requestAccessibility, requestScreenRecording } from '../permissions';
import { captureScreen } from './screenshot';
import { createSuggestionWindow, destroySuggestion, getSuggestionWindow } from './suggestion-window';
import { getShortcuts } from '../shortcuts';
import { getActiveSearchSpaceId } from '../active-search-space';
import { trackEvent } from '../analytics';

let currentShortcut = '';
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
  const windowTitle = getWindowTitle();
  savedClipboard = clipboard.readText();

  const screenshot = await captureScreen();
  if (!screenshot) {
    console.error('[autocomplete] Screenshot capture failed');
    return;
  }

  const searchSpaceId = await getActiveSearchSpaceId();
  if (!searchSpaceId) {
    console.warn('[autocomplete] No active search space. Select a search space first.');
    return;
  }
  trackEvent('desktop_autocomplete_triggered', { search_space_id: searchSpaceId });
  const cursor = screen.getCursorScreenPoint();
  const win = createSuggestionWindow(cursor.x, cursor.y);

  win.webContents.once('did-finish-load', () => {
    const sw = getSuggestionWindow();
    setTimeout(() => {
      if (sw && !sw.isDestroyed()) {
        sw.webContents.send(IPC_CHANNELS.AUTOCOMPLETE_CONTEXT, {
          screenshot,
          searchSpaceId,
          appName: sourceApp,
          windowTitle,
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

let ipcRegistered = false;

function registerIpcHandlers(): void {
  if (ipcRegistered) return;
  ipcRegistered = true;

  ipcMain.handle(IPC_CHANNELS.ACCEPT_SUGGESTION, async (_event, text: string) => {
    trackEvent('desktop_autocomplete_accepted');
    await acceptAndInject(text);
  });
  ipcMain.handle(IPC_CHANNELS.DISMISS_SUGGESTION, () => {
    trackEvent('desktop_autocomplete_dismissed');
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

function autocompleteHandler(): void {
  const sw = getSuggestionWindow();
  if (sw && !sw.isDestroyed()) {
    destroySuggestion();
    return;
  }
  triggerAutocomplete();
}

async function registerShortcut(): Promise<void> {
  const shortcuts = await getShortcuts();
  currentShortcut = shortcuts.autocomplete;

  const ok = globalShortcut.register(currentShortcut, autocompleteHandler);

  if (!ok) {
    console.error(`[autocomplete] Failed to register shortcut ${currentShortcut}`);
  } else {
    console.log(`[autocomplete] Registered shortcut ${currentShortcut}`);
  }
}

export async function registerAutocomplete(): Promise<void> {
  registerIpcHandlers();
  await registerShortcut();
}

export function unregisterAutocomplete(): void {
  if (currentShortcut) globalShortcut.unregister(currentShortcut);
  destroySuggestion();
}

export async function reregisterAutocomplete(): Promise<void> {
  unregisterAutocomplete();
  await registerShortcut();
}
