import { app, globalShortcut, Menu, nativeImage, Tray, type NativeImage } from 'electron';
import path from 'path';
import { runGeneralAssistShortcut } from './general-assist';
import { runScreenshotAssistShortcut } from './screen-capture';
import { showMainWindow } from './window';
import { getShortcuts } from './shortcuts';
import { trackEvent } from './analytics';

let tray: Tray | null = null;
let registeredGeneralAssist: string | null = null;
let registeredScreenshotAssist: string | null = null;

function buildContextMenu(screenshotAccelerator: string): Menu {
  return Menu.buildFromTemplate([
    { label: 'Open SurfSense', click: () => showMainWindow('tray_menu') },
    {
      label: 'Take Screenshot\u2026',
      accelerator: screenshotAccelerator || undefined,
      click: () => {
        trackEvent('desktop_tray_screenshot_clicked');
        void Promise.resolve(runScreenshotAssistShortcut()).catch((err) => {
          console.error('[tray] Screenshot Assist failed:', err);
        });
      },
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        trackEvent('desktop_tray_quit_clicked');
        app.exit(0);
      },
    },
  ]);
}

function getTrayIcon(): NativeImage {
  const iconName =
    process.platform === 'darwin'
      ? 'iconTemplate.png'
      : process.platform === 'win32'
        ? 'icon.ico'
        : 'icon.png';
  const iconPath = app.isPackaged
    ? path.join(process.resourcesPath, 'assets', iconName)
    : path.join(__dirname, '..', 'assets', iconName);
  const img = nativeImage.createFromPath(iconPath);
  if (process.platform === 'darwin') {
    img.setTemplateImage(true);
    return img;
  }
  return img.resize({ width: 16, height: 16 });
}

function registerOne(
  previous: string | null,
  accelerator: string,
  onFire: () => void | Promise<void>,
  label: string
): string | null {
  if (previous) {
    globalShortcut.unregister(previous);
  }
  if (!accelerator) return null;
  try {
    const ok = globalShortcut.register(accelerator, () => {
      void Promise.resolve(onFire());
    });
    if (ok) {
      console.log(`[hotkeys] Register ${label} ${accelerator}: OK`);
      return accelerator;
    }
    console.warn(`[hotkeys] Register ${label} ${accelerator}: FAILED (OS or another app may own this chord)`);
  } catch (err) {
    console.error(`[tray] Error registering ${label} shortcut:`, err);
  }
  return null;
}

export async function createTray(): Promise<void> {
  if (tray) return;

  tray = new Tray(getTrayIcon());
  tray.setToolTip('SurfSense');

  const shortcuts = await getShortcuts();
  tray.setContextMenu(buildContextMenu(shortcuts.screenshotAssist));
  tray.on('double-click', () => showMainWindow('tray_click'));

  registeredGeneralAssist = registerOne(
    null,
    shortcuts.generalAssist,
    runGeneralAssistShortcut,
    'General Assist'
  );
  registeredScreenshotAssist = registerOne(
    null,
    shortcuts.screenshotAssist,
    runScreenshotAssistShortcut,
    'Screenshot Assist'
  );
}

export async function reregisterGeneralAssist(): Promise<void> {
  const shortcuts = await getShortcuts();
  registeredGeneralAssist = registerOne(
    registeredGeneralAssist,
    shortcuts.generalAssist,
    runGeneralAssistShortcut,
    'General Assist'
  );
}

export async function reregisterScreenshotAssist(): Promise<void> {
  const shortcuts = await getShortcuts();
  registeredScreenshotAssist = registerOne(
    registeredScreenshotAssist,
    shortcuts.screenshotAssist,
    runScreenshotAssistShortcut,
    'Screenshot Assist'
  );
  tray?.setContextMenu(buildContextMenu(shortcuts.screenshotAssist));
}

export function destroyTray(): void {
  if (registeredGeneralAssist) {
    globalShortcut.unregister(registeredGeneralAssist);
    registeredGeneralAssist = null;
  }
  if (registeredScreenshotAssist) {
    globalShortcut.unregister(registeredScreenshotAssist);
    registeredScreenshotAssist = null;
  }
  tray?.destroy();
  tray = null;
}
