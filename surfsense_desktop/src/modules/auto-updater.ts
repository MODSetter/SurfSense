import { app, dialog } from 'electron';
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

let listenersRegistered = false;

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
    trackEvent('desktop_update_available', {
      current_version: version,
      new_version: info.version,
    });
  });

  autoUpdater.on('update-downloaded', (info: UpdateInfo) => {
    console.log(`Update downloaded: ${info.version}`);
    trackEvent('desktop_update_downloaded', {
      current_version: version,
      new_version: info.version,
    });
    dialog.showMessageBox({
      type: 'info',
      buttons: ['Restart', 'Later'],
      defaultId: 0,
      title: 'Update Ready',
      message: `Version ${info.version} has been downloaded. Restart to apply the update.`,
    }).then(({ response }: { response: number }) => {
      if (response === 0) {
        trackEvent('desktop_update_install_accepted', { new_version: info.version });
        autoUpdater.quitAndInstall();
      } else {
        trackEvent('desktop_update_install_deferred', { new_version: info.version });
      }
    });
  });

  autoUpdater.on('error', (err: Error) => {
    console.log('Auto-updater: update check skipped —', err.message?.split('\n')[0]);
    trackEvent('desktop_update_error', {
      message: err.message?.split('\n')[0],
    });
  });
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
    const result = await new Promise<'available' | 'not-available'>((resolve, reject) => {
      const cleanup = () => {
        autoUpdater.removeListener('update-available', onAvailable);
        autoUpdater.removeListener('update-not-available', onNotAvailable);
        autoUpdater.removeListener('error', onError);
      };
      const onAvailable = (info: UpdateInfo) => {
        cleanup();
        void dialog.showMessageBox({
          type: 'info',
          title: 'Update Available',
          message: `Version ${info.version} is available and will download in the background.`,
        });
        resolve('available');
      };
      const onNotAvailable = () => {
        cleanup();
        resolve('not-available');
      };
      const onError = (err: Error) => {
        cleanup();
        reject(err);
      };

      autoUpdater.once('update-available', onAvailable);
      autoUpdater.once('update-not-available', onNotAvailable);
      autoUpdater.once('error', onError);
      autoUpdater.checkForUpdates().catch((err: Error) => {
        cleanup();
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
    await dialog.showMessageBox({
      type: 'error',
      title: 'Update Check Failed',
      message: err instanceof Error ? err.message : String(err),
    });
  }
}
