import { app } from 'electron';
import fs from 'fs';
import os from 'os';
import path from 'path';

// ---------------------------------------------------------------------------
// Launch on system startup ("auto-launch" / "open at login").
//
// macOS + Windows : uses Electron's built-in `app.setLoginItemSettings()`.
// Linux           : writes a freedesktop autostart `.desktop` file into
//                   `~/.config/autostart/`. Electron's API is a no-op there.
//
// The OS is the source of truth for whether we're enabled (so a user who
// disables us via System Settings / GNOME Tweaks isn't silently overridden).
// We persist a small companion record in electron-store for things the OS
// can't tell us — currently just `openAsHidden`, since on Windows we encode
// it as a CLI arg and on Linux as part of the Exec line, but on a fresh
// startup we still want the renderer toggle to reflect the user's intent.
// ---------------------------------------------------------------------------

const STORE_KEY = 'launchAtLogin';
const HIDDEN_FLAG = '--hidden';
const LINUX_DESKTOP_FILENAME = 'surfsense.desktop';

export interface AutoLaunchState {
  enabled: boolean;
  openAsHidden: boolean;
  supported: boolean;
}

interface PersistedState {
  enabled: boolean;
  openAsHidden: boolean;
  // True once we've run the first-launch defaults (opt-in to auto-launch).
  // We never re-apply defaults if this is set, so a user who has explicitly
  // turned auto-launch off stays off forever.
  defaultsApplied: boolean;
}

const DEFAULTS: PersistedState = {
  enabled: false,
  openAsHidden: true,
  defaultsApplied: false,
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- lazily imported ESM module; matches shortcuts.ts pattern
let store: any = null;

async function getStore() {
  if (!store) {
    const { default: Store } = await import('electron-store');
    store = new Store({
      name: 'auto-launch',
      defaults: { [STORE_KEY]: DEFAULTS },
    });
  }
  return store;
}

async function readPersisted(): Promise<PersistedState> {
  const s = await getStore();
  const stored = s.get(STORE_KEY) as Partial<PersistedState> | undefined;
  return { ...DEFAULTS, ...(stored ?? {}) };
}

async function writePersisted(next: PersistedState): Promise<void> {
  const s = await getStore();
  s.set(STORE_KEY, next);
}

// ---------------------------------------------------------------------------
// Platform support
// ---------------------------------------------------------------------------

// Auto-launch only makes sense for the packaged app — in dev `process.execPath`
// is the local Electron binary, so registering it would point the OS at a
// throwaway path the next time the dev server isn't running.
function isSupported(): boolean {
  if (!app.isPackaged) return false;
  return ['darwin', 'win32', 'linux'].includes(process.platform);
}

// ---------------------------------------------------------------------------
// Linux: ~/.config/autostart/surfsense.desktop
// ---------------------------------------------------------------------------

function linuxAutostartDir(): string {
  const xdg = process.env.XDG_CONFIG_HOME;
  const base = xdg && xdg.length > 0 ? xdg : path.join(os.homedir(), '.config');
  return path.join(base, 'autostart');
}

function linuxAutostartFile(): string {
  return path.join(linuxAutostartDir(), LINUX_DESKTOP_FILENAME);
}

// AppImages move around with the user — `process.execPath` points at a temp
// mount, so we have to use the original AppImage path exposed via env.
function linuxExecPath(): string {
  return process.env.APPIMAGE && process.env.APPIMAGE.length > 0
    ? process.env.APPIMAGE
    : process.execPath;
}

function escapeDesktopExecArg(value: string): string {
  // Freedesktop `.desktop` Exec values require quoted args when spaces are
  // present. We keep this intentionally minimal and escape only characters
  // that can break quoted parsing.
  return `"${value.replace(/(["\\`$])/g, '\\$1')}"`;
}

function writeLinuxDesktopFile(openAsHidden: boolean): void {
  const exec = escapeDesktopExecArg(linuxExecPath());
  const args = openAsHidden ? ` ${HIDDEN_FLAG}` : '';
  const contents = [
    '[Desktop Entry]',
    'Type=Application',
    'Version=1.0',
    'Name=SurfSense',
    'Comment=AI-powered research assistant',
    `Exec=${exec}${args}`,
    'Terminal=false',
    'Categories=Utility;Office;',
    'X-GNOME-Autostart-enabled=true',
    `X-GNOME-Autostart-Delay=${openAsHidden ? '5' : '0'}`,
    '',
  ].join('\n');

  fs.mkdirSync(linuxAutostartDir(), { recursive: true });
  fs.writeFileSync(linuxAutostartFile(), contents, { mode: 0o644 });
}

function removeLinuxDesktopFile(): void {
  try {
    fs.unlinkSync(linuxAutostartFile());
  } catch (err: unknown) {
    if ((err as NodeJS.ErrnoException)?.code !== 'ENOENT') throw err;
  }
}

function readLinuxDesktopFile(): boolean {
  return fs.existsSync(linuxAutostartFile());
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function getAutoLaunchState(): Promise<AutoLaunchState> {
  const supported = isSupported();
  const persisted = await readPersisted();

  if (!supported) {
    return { enabled: false, openAsHidden: persisted.openAsHidden, supported: false };
  }

  // Trust the OS state — the user may have disabled it from system settings.
  return { enabled: readOsEnabled(), openAsHidden: persisted.openAsHidden, supported: true };
}

export async function setAutoLaunch(
  enabled: boolean,
  openAsHidden: boolean = DEFAULTS.openAsHidden,
): Promise<AutoLaunchState> {
  const supported = isSupported();

  if (!supported) {
    return { enabled: false, openAsHidden, supported: false };
  }

  applySystemRegistration(enabled, openAsHidden);
  // Preserve `defaultsApplied` (and any future fields) — and explicitly
  // mark them as applied, since the user has now made an intentional choice.
  await writePersisted({ enabled, openAsHidden, defaultsApplied: true });
  return { enabled, openAsHidden, supported: true };
}

function applySystemRegistration(enabled: boolean, openAsHidden: boolean): void {
  if (process.platform === 'linux') {
    if (enabled) writeLinuxDesktopFile(openAsHidden);
    else removeLinuxDesktopFile();
    return;
  }

  if (!enabled) {
    app.setLoginItemSettings({ openAtLogin: false });
    return;
  }

  if (process.platform === 'win32') {
    // On Windows we can't tell the OS to "launch hidden" — instead we pass an
    // arg the app introspects on boot to skip showing the main window.
    app.setLoginItemSettings({
      openAtLogin: true,
      args: openAsHidden ? [HIDDEN_FLAG] : [],
    });
    return;
  }

  // darwin
  app.setLoginItemSettings({
    openAtLogin: true,
    openAsHidden,
  });
}

// First-launch opt-in: register SurfSense as a hidden login item so the tray,
// global shortcuts, and folder watchers are ready right after the user signs
// in. Runs at most once per installation — the `defaultsApplied` flag is
// flipped before we ever touch the OS so a failure to register doesn't cause
// us to retry on every boot, and a user who turns the toggle off afterwards
// is never silently re-enabled.
//
// Returns whether the defaults were actually applied this boot, so callers
// can fire an analytics event without coupling this module to PostHog.
export async function applyAutoLaunchDefaults(): Promise<boolean> {
  if (!isSupported()) return false;
  const persisted = await readPersisted();
  if (persisted.defaultsApplied) return false;

  // Mark the defaults as applied *first*. If `applySystemRegistration`
  // throws (e.g. read-only home dir on Linux), we'd rather silently leave
  // the user un-registered than spam them with a failed registration on
  // every single boot.
  const next: PersistedState = {
    enabled: true,
    openAsHidden: true,
    defaultsApplied: true,
  };

  try {
    applySystemRegistration(true, true);
  } catch (err) {
    console.error('[auto-launch] First-run registration failed:', err);
    next.enabled = false;
  }

  await writePersisted(next);
  return next.enabled;
}

// Called once at startup. Goal:
//   * If the OS-level entry is already enabled, re-assert it so a moved
//     binary (Windows reinstall to a new dir, Linux AppImage moved by user)
//     gets its registered path refreshed.
//   * If the OS-level entry has been disabled — typically because the user
//     turned it off in System Settings / GNOME Tweaks — *respect that* and
//     reconcile our persisted state to match. We never silently re-enable
//     a login item the user explicitly turned off.
export async function syncAutoLaunchOnStartup(): Promise<void> {
  if (!isSupported()) return;

  const persisted = await readPersisted();
  const osEnabled = readOsEnabled();

  if (!osEnabled) {
    // User (or some other tool) turned us off out-of-band. Don't re-enable;
    // just bring our persisted state in sync so the settings UI reflects
    // reality on the next render.
    if (persisted.enabled) {
      await writePersisted({ ...persisted, enabled: false });
    }
    return;
  }

  // OS says we're enabled — refresh the registration so the recorded path /
  // args match this binary. Idempotent on macOS; corrects path drift on
  // Windows and Linux. If our persisted state was somehow stale we also
  // bring it back in line.
  try {
    applySystemRegistration(true, persisted.openAsHidden);
    if (!persisted.enabled) {
      await writePersisted({ ...persisted, enabled: true });
    }
  } catch (err) {
    console.error('[auto-launch] Failed to re-assert login item:', err);
  }
}

function readOsEnabled(): boolean {
  if (process.platform === 'linux') return readLinuxDesktopFile();
  return app.getLoginItemSettings().openAtLogin;
}

// True when the OS launched us as part of login (used for analytics).
export function wasLaunchedAtLogin(): boolean {
  if (process.argv.includes(HIDDEN_FLAG)) return true;
  if (process.platform === 'darwin') {
    const settings = app.getLoginItemSettings();
    return settings.wasOpenedAtLogin || settings.wasOpenedAsHidden;
  }
  return false;
}

// Used for boot UI behavior. On macOS we only start hidden when the OS
// explicitly launched the app as hidden, not merely "at login".
export function shouldStartHidden(): boolean {
  if (process.argv.includes(HIDDEN_FLAG)) return true;
  if (process.platform === 'darwin') {
    const settings = app.getLoginItemSettings();
    return settings.wasOpenedAsHidden;
  }
  return false;
}
