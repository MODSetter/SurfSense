import { app, Menu, shell } from 'electron';
import {
  checkForUpdatesManually,
  getUpdateMenuState,
  installDownloadedUpdate,
  onUpdateMenuStateChange,
} from './auto-updater';

let updateMenuListenerRegistered = false;

function getUpdateMenuItem(): Electron.MenuItemConstructorOptions {
  const state = getUpdateMenuState();

  if (state.status === 'downloading') {
    return {
      label: 'Downloading...',
      enabled: false,
    };
  }

  if (state.status === 'ready') {
    return {
      label: 'Install and Restart',
      click: () => {
        installDownloadedUpdate();
      },
    };
  }

  return {
    label: 'Check for Updates...',
    click: () => {
      void checkForUpdatesManually();
    },
  };
}

const privacyPolicyItem: Electron.MenuItemConstructorOptions = {
  label: 'Privacy Policy',
  click: () => {
    void shell.openExternal('https://www.surfsense.com/privacy');
  },
};

const termsOfServiceItem: Electron.MenuItemConstructorOptions = {
  label: 'Terms of Service',
  click: () => {
    void shell.openExternal('https://www.surfsense.com/terms');
  },
};

export function setupMenu(): void {
  if (!updateMenuListenerRegistered) {
    updateMenuListenerRegistered = true;
    onUpdateMenuStateChange(() => {
      setupMenu();
    });
  }

  const isMac = process.platform === 'darwin';
  const updateMenuItem = getUpdateMenuItem();
  const template: Electron.MenuItemConstructorOptions[] = [
    ...(isMac
      ? [{
          label: app.name,
          submenu: [
            { role: 'about' as const },
            updateMenuItem,
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
    {
      role: 'help' as const,
      submenu: [
        ...(!isMac
          ? [
              updateMenuItem,
              { type: 'separator' as const },
            ]
          : []),
        privacyPolicyItem,
        termsOfServiceItem,
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}
