import { app, globalShortcut, Menu, nativeImage, Tray, type NativeImage } from 'electron';
import path from 'path';
import { runGeneralAssistShortcut } from './general-assist';
import { showMainWindow } from './window';
import { getShortcuts } from './shortcuts';
import { trackEvent } from './analytics';

let tray: Tray | null = null;
let currentShortcut: string | null = null;

function getTrayIcon(): NativeImage {
  const iconName = process.platform === 'win32' ? 'icon.ico' : 'icon.png';
  const iconPath = app.isPackaged
    ? path.join(process.resourcesPath, 'assets', iconName)
    : path.join(__dirname, '..', 'assets', iconName);
  const img = nativeImage.createFromPath(iconPath);
  return img.resize({ width: 16, height: 16 });
}

function registerShortcut(accelerator: string): void {
  if (currentShortcut) {
    globalShortcut.unregister(currentShortcut);
    currentShortcut = null;
  }
  if (!accelerator) return;
  try {
    const ok = globalShortcut.register(accelerator, () => {
      void runGeneralAssistShortcut();
    });
    if (ok) {
      currentShortcut = accelerator;
      console.log(`[general-assist] Register ${accelerator}: OK`);
    } else {
      console.warn(`[general-assist] Register ${accelerator}: FAILED (OS or another app may own this chord)`);
    }
  } catch (err) {
    console.error(`[tray] Error registering General Assist shortcut:`, err);
  }
}

export async function createTray(): Promise<void> {
  if (tray) return;

  tray = new Tray(getTrayIcon());
  tray.setToolTip('SurfSense');

  const contextMenu = Menu.buildFromTemplate([
    { label: 'Open SurfSense', click: () => showMainWindow('tray_menu') },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        trackEvent('desktop_tray_quit_clicked');
        app.exit(0);
      },
    },
  ]);

  tray.setContextMenu(contextMenu);
  tray.on('double-click', () => showMainWindow('tray_click'));

  const shortcuts = await getShortcuts();
  registerShortcut(shortcuts.generalAssist);
}

export async function reregisterGeneralAssist(): Promise<void> {
  const shortcuts = await getShortcuts();
  registerShortcut(shortcuts.generalAssist);
}

export function destroyTray(): void {
  if (currentShortcut) {
    globalShortcut.unregister(currentShortcut);
    currentShortcut = null;
  }
  tray?.destroy();
  tray = null;
}
