import { app, globalShortcut, Menu, nativeImage, Tray } from 'electron';
import path from 'path';
import { getMainWindow, createMainWindow } from './window';
import { getShortcuts } from './shortcuts';
import { trackEvent } from './analytics';

let tray: Tray | null = null;
let currentShortcut: string | null = null;

function getTrayIcon(): nativeImage {
  const iconName = process.platform === 'win32' ? 'icon.ico' : 'icon.png';
  const iconPath = app.isPackaged
    ? path.join(process.resourcesPath, 'assets', iconName)
    : path.join(__dirname, '..', 'assets', iconName);
  const img = nativeImage.createFromPath(iconPath);
  return img.resize({ width: 16, height: 16 });
}

function showMainWindow(source: 'tray_click' | 'tray_menu' | 'shortcut' = 'tray_click'): void {
  const existing = getMainWindow();
  const reopened = !existing || existing.isDestroyed();
  if (reopened) {
    createMainWindow('/dashboard');
  } else {
    existing.show();
    existing.focus();
  }
  trackEvent('desktop_main_window_shown', { source, reopened });
}

function registerShortcut(accelerator: string): void {
  if (currentShortcut) {
    globalShortcut.unregister(currentShortcut);
    currentShortcut = null;
  }
  if (!accelerator) return;
  try {
    const ok = globalShortcut.register(accelerator, () => showMainWindow('shortcut'));
    if (ok) {
      currentShortcut = accelerator;
    } else {
      console.warn(`[tray] Failed to register General Assist shortcut: ${accelerator}`);
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
