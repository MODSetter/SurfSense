import { app, dialog } from 'electron';

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
  });

  autoUpdater.on('update-downloaded', (info: { version: string }) => {
    console.log(`Update downloaded: ${info.version}`);
    dialog.showMessageBox({
      type: 'info',
      buttons: ['Restart', 'Later'],
      defaultId: 0,
      title: 'Update Ready',
      message: `Version ${info.version} has been downloaded. Restart to apply the update.`,
    }).then(({ response }: { response: number }) => {
      if (response === 0) {
        autoUpdater.quitAndInstall();
      }
    });
  });

  autoUpdater.on('error', (err: Error) => {
    console.log('Auto-updater: update check skipped —', err.message?.split('\n')[0]);
  });

  autoUpdater.checkForUpdates().catch(() => {});
}
