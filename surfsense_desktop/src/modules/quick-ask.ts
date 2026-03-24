import { clipboard, globalShortcut } from 'electron';
import { IPC_CHANNELS } from '../ipc/channels';
import { getMainWindow } from './window';

const SHORTCUT = 'CommandOrControl+Option+S';

export function registerQuickAsk(): void {
  const ok = globalShortcut.register(SHORTCUT, () => {
    const win = getMainWindow();
    if (!win) return;

    const text = clipboard.readText().trim();
    if (!text) return;

    if (win.isMinimized()) win.restore();
    win.show();
    win.focus();

    win.webContents.send(IPC_CHANNELS.QUICK_ASK_TEXT, text);
  });

  if (!ok) {
    console.log(`Quick-ask: failed to register ${SHORTCUT}`);
  }
}

export function unregisterQuickAsk(): void {
  globalShortcut.unregister(SHORTCUT);
}
