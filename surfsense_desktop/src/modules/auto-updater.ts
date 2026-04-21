import { app, dialog } from 'electron';
import { trackEvent } from './analytics';

const SEMVER_RE = /^\d+\.\d+\.\d+/;

export function setupAutoUpdater(): void {
  if (!app.isPackaged) return;

  const version = app.getVersion();
  if (!SEMVER_RE.test(version)) {
    console.log(`Auto-updater: skipping — "${version}" is not valid semver`);
    return;
  }

  const { autoUpdater } = require('electron-updater');

  autoUpdater.autoDownload = true;

  autoUpdater.on('update-available', (info: { version: string }) => {
    console.log(`Update available: ${info.version}`);
    trackEvent('desktop_update_available', {
      current_version: version,
      new_version: info.version,
    });
  });

  autoUpdater.on('update-downloaded', (info: { version: string }) => {
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

  autoUpdater.checkForUpdates().catch(() => {});
}
