import { ipcMain } from 'electron';
import { IPC_CHANNELS } from '../ipc/channels';

let lastClipboardContent = '';

export function setClipboardContent(text: string): void {
  lastClipboardContent = text;
}

export function registerClipboardHandlers(): void {
  ipcMain.handle(IPC_CHANNELS.GET_CLIPBOARD_CONTENT, () => {
    return lastClipboardContent;
  });
}
