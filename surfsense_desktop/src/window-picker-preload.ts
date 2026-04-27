import { contextBridge, ipcRenderer } from 'electron';
import { IPC_CHANNELS } from './ipc/channels';

contextBridge.exposeInMainWorld('surfsenseWindowPick', {
  list: () =>
    ipcRenderer.invoke(IPC_CHANNELS.WINDOW_PICK_LIST) as Promise<
      { id: string; name: string; thumbDataUrl: string }[]
    >,
  submit: (sourceId: string) => {
    ipcRenderer.send(IPC_CHANNELS.WINDOW_PICK_SUBMIT, sourceId);
  },
  cancel: () => {
    ipcRenderer.send(IPC_CHANNELS.WINDOW_PICK_CANCEL);
  },
});
