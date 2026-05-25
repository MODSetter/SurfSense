import { app, BrowserWindow, dialog } from 'electron';
import { IPC_CHANNELS } from '../ipc/channels';
import { trackEvent } from './analytics';

const SEMVER_RE = /^\d+\.\d+\.\d+/;

type AutoUpdater = {
  autoDownload: boolean;
  on(event: string, listener: (...args: any[]) => void): void;
  once(event: string, listener: (...args: any[]) => void): void;
  removeListener(event: string, listener: (...args: any[]) => void): void;
  checkForUpdates(): Promise<unknown>;
  quitAndInstall(): void;
};

type UpdateInfo = {
  version: string;
};

type UpdateMenuState =
  | { status: 'idle' }
  | { status: 'downloading'; version: string }
  | { status: 'ready'; version: string };

let listenersRegistered = false;
let updateMenuState: UpdateMenuState = { status: 'idle' };
const updateMenuStateListeners = new Set<(state: UpdateMenuState) => void>();

export function getUpdateMenuState(): UpdateMenuState {
  return updateMenuState;
}

export function onUpdateMenuStateChange(listener: (state: UpdateMenuState) => void): () => void {
  updateMenuStateListeners.add(listener);
  return () => {
    updateMenuStateListeners.delete(listener);
  };
}

function setUpdateMenuState(state: UpdateMenuState): void {
  updateMenuState = state;
  for (const listener of updateMenuStateListeners) {
    listener(state);
  }
}

function getAutoUpdater(): AutoUpdater {
  const { autoUpdater } = require('electron-updater');
  return autoUpdater as AutoUpdater;
}

function configureAutoUpdater(autoUpdater: AutoUpdater): void {
  autoUpdater.autoDownload = true;

  if (listenersRegistered) return;
  listenersRegistered = true;

  const version = app.getVersion();

  autoUpdater.on('update-available', (info: UpdateInfo) => {
    console.log(`Update available: ${info.version}`);
    setUpdateMenuState({ status: 'downloading', version: info.version });
    trackEvent('desktop_update_available', {
      current_version: version,
      new_version: info.version,
    });
  });

  autoUpdater.on('update-downloaded', (info: UpdateInfo) => {
    console.log(`Update downloaded: ${info.version}`);
    setUpdateMenuState({ status: 'ready', version: info.version });
    trackEvent('desktop_update_downloaded', {
      current_version: version,
      new_version: info.version,
    });
    notifyRenderersUpdateDownloaded(info);
  });

  autoUpdater.on('update-not-available', () => {
    setUpdateMenuState({ status: 'idle' });
  });

  autoUpdater.on('error', (err: Error) => {
    setUpdateMenuState({ status: 'idle' });
    console.log('Auto-updater: update check skipped —', err.message?.split('\n')[0]);
    trackEvent('desktop_update_error', {
      message: err.message?.split('\n')[0],
    });
  });
}

function notifyRenderersUpdateDownloaded(info: UpdateInfo): void {
  for (const win of BrowserWindow.getAllWindows()) {
    if (!win.isDestroyed()) {
      win.webContents.send(IPC_CHANNELS.UPDATE_DOWNLOADED, {
        version: info.version,
      });
    }
  }
}

export function installDownloadedUpdate(): void {
  const autoUpdater = getAutoUpdater();
  trackEvent('desktop_update_install_accepted', { source: 'renderer_prompt' });
  autoUpdater.quitAndInstall();
}

export function setupAutoUpdater(): void {
  if (!app.isPackaged) return;

  const version = app.getVersion();
  if (!SEMVER_RE.test(version)) {
    console.log(`Auto-updater: skipping - "${version}" is not valid semver`);
    return;
  }

  const autoUpdater = getAutoUpdater();
  configureAutoUpdater(autoUpdater);

  autoUpdater.checkForUpdates().catch(() => {});
}

export async function checkForUpdatesManually(): Promise<void> {
  const currentState = getUpdateMenuState();
  if (currentState.status === 'ready') {
    installDownloadedUpdate();
    return;
  }
  if (currentState.status === 'downloading') return;

  if (!app.isPackaged) {
    await dialog.showMessageBox({
      type: 'info',
      title: 'Updates Unavailable',
      message: 'Updates are only available in packaged builds.',
    });
    return;
  }

  const version = app.getVersion();
  if (!SEMVER_RE.test(version)) {
    await dialog.showMessageBox({
      type: 'info',
      title: 'Updates Unavailable',
      message: `Version "${version}" is not a valid release version, so updates cannot be checked.`,
    });
    return;
  }

  const autoUpdater = getAutoUpdater();
  configureAutoUpdater(autoUpdater);

  try {
    const result = await new Promise<'not-available' | 'downloaded'>((resolve, reject) => {
      const cleanup = () => {
        autoUpdater.removeListener('update-available', onAvailable);
        autoUpdater.removeListener('update-not-available', onNotAvailable);
        autoUpdater.removeListener('update-downloaded', onDownloaded);
        autoUpdater.removeListener('error', onError);
      };
      const onAvailable = () => {};
      const onNotAvailable = () => {
        cleanup();
        resolve('not-available');
      };
      const onDownloaded = () => {
        cleanup();
        resolve('downloaded');
      };
      const onError = (err: Error) => {
        cleanup();
        reject(err);
      };

      autoUpdater.once('update-available', onAvailable);
      autoUpdater.once('update-not-available', onNotAvailable);
      autoUpdater.once('update-downloaded', onDownloaded);
      autoUpdater.once('error', onError);
      autoUpdater.checkForUpdates().catch((err: Error) => {
        cleanup();
        setUpdateMenuState({ status: 'idle' });
        reject(err);
      });
    });

    if (result === 'not-available') {
      await dialog.showMessageBox({
        type: 'info',
        title: 'No Updates Available',
        message: "You're up to date.",
      });
    }
  } catch (err) {
    setUpdateMenuState({ status: 'idle' });
    await dialog.showMessageBox({
      type: 'error',
      title: 'Update Check Failed',
      message: err instanceof Error ? err.message : String(err),
    });
  }
}
