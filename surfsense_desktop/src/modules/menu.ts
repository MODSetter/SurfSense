import { Menu } from 'electron';

export function setupMenu(): void {
  const isMac = process.platform === 'darwin';
  const template: Electron.MenuItemConstructorOptions[] = [
    ...(isMac ? [{ role: 'appMenu' as const }] : []),
    { role: 'fileMenu' as const },
    { role: 'editMenu' as const },
    { role: 'viewMenu' as const },
    { role: 'windowMenu' as const },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}
