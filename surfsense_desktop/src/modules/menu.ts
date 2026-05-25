import { app, Menu } from 'electron';
import { checkForUpdatesManually } from './auto-updater';

const checkForUpdatesItem: Electron.MenuItemConstructorOptions = {
  label: 'Check for Updates...',
  click: () => {
    void checkForUpdatesManually();
  },
};

export function setupMenu(): void {
  const isMac = process.platform === 'darwin';
  const template: Electron.MenuItemConstructorOptions[] = [
    ...(isMac
      ? [{
          label: app.name,
          submenu: [
            { role: 'about' as const },
            checkForUpdatesItem,
            { type: 'separator' as const },
            { role: 'services' as const },
            { type: 'separator' as const },
            { role: 'hide' as const },
            { role: 'hideOthers' as const },
            { role: 'unhide' as const },
            { type: 'separator' as const },
            { role: 'quit' as const },
          ],
        }]
      : []),
    { role: 'fileMenu' as const },
    { role: 'editMenu' as const },
    { role: 'viewMenu' as const },
    { role: 'windowMenu' as const },
    ...(!isMac
      ? [{
          role: 'help' as const,
          submenu: [
            checkForUpdatesItem,
          ],
        }]
      : []),
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}
