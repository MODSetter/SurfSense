import { BrowserWindow, dialog } from 'electron';
import chokidar from 'chokidar';
import * as path from 'path';
import * as fs from 'fs';
import { IPC_CHANNELS } from '../ipc/channels';

export interface WatchedFolderConfig {
  path: string;
  name: string;
  excludePatterns: string[];
  fileExtensions: string[] | null;
  connectorId: number;
  searchSpaceId: number;
  active: boolean;
}

interface WatcherEntry {
  config: WatchedFolderConfig;
  watcher: chokidar.FSWatcher | null;
}

const STORE_KEY = 'watchedFolders';
let store: any = null;
let watchers: Map<string, WatcherEntry> = new Map();

async function getStore() {
  if (!store) {
    const { default: Store } = await import('electron-store');
    store = new Store({
      name: 'folder-watcher',
      defaults: {
        [STORE_KEY]: [] as WatchedFolderConfig[],
      },
    });
  }
  return store;
}

function getMainWindow(): BrowserWindow | null {
  const windows = BrowserWindow.getAllWindows();
  return windows.length > 0 ? windows[0] : null;
}

function sendToRenderer(channel: string, data: any) {
  const win = getMainWindow();
  if (win && !win.isDestroyed()) {
    win.webContents.send(channel, data);
  }
}

function startWatcher(config: WatchedFolderConfig) {
  if (watchers.has(config.path)) {
    return;
  }

  const ignored = [
    /(^|[/\\])\../, // dotfiles by default
    ...config.excludePatterns.map((p) => `**/${p}/**`),
  ];

  const watcher = chokidar.watch(config.path, {
    persistent: true,
    ignoreInitial: false,
    awaitWriteFinish: {
      stabilityThreshold: 500,
      pollInterval: 100,
    },
    ignored,
  });

  let ready = false;

  watcher.on('ready', () => {
    ready = true;
    sendToRenderer(IPC_CHANNELS.FOLDER_SYNC_WATCHER_READY, {
      connectorId: config.connectorId,
      folderPath: config.path,
    });
  });

  const handleFileEvent = (filePath: string, action: string) => {
    if (!ready) return;

    const relativePath = path.relative(config.path, filePath);

    if (
      config.fileExtensions &&
      config.fileExtensions.length > 0
    ) {
      const ext = path.extname(filePath).toLowerCase();
      if (!config.fileExtensions.includes(ext)) return;
    }

    sendToRenderer(IPC_CHANNELS.FOLDER_SYNC_FILE_CHANGED, {
      connectorId: config.connectorId,
      searchSpaceId: config.searchSpaceId,
      folderPath: config.path,
      relativePath,
      fullPath: filePath,
      action,
      timestamp: Date.now(),
    });
  };

  watcher.on('add', (fp) => handleFileEvent(fp, 'add'));
  watcher.on('change', (fp) => handleFileEvent(fp, 'change'));
  watcher.on('unlink', (fp) => handleFileEvent(fp, 'unlink'));

  watchers.set(config.path, { config, watcher });
}

function stopWatcher(folderPath: string) {
  const entry = watchers.get(folderPath);
  if (entry?.watcher) {
    entry.watcher.close();
  }
  watchers.delete(folderPath);
}

export async function selectFolder(): Promise<string | null> {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory'],
    title: 'Select a folder to watch',
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
}

export async function addWatchedFolder(
  config: WatchedFolderConfig
): Promise<WatchedFolderConfig[]> {
  const s = await getStore();
  const folders: WatchedFolderConfig[] = s.get(STORE_KEY, []);

  const existing = folders.findIndex((f: WatchedFolderConfig) => f.path === config.path);
  if (existing >= 0) {
    folders[existing] = config;
  } else {
    folders.push(config);
  }

  s.set(STORE_KEY, folders);

  if (config.active) {
    startWatcher(config);
  }

  return folders;
}

export async function removeWatchedFolder(
  folderPath: string
): Promise<WatchedFolderConfig[]> {
  const s = await getStore();
  const folders: WatchedFolderConfig[] = s.get(STORE_KEY, []);
  const updated = folders.filter((f: WatchedFolderConfig) => f.path !== folderPath);
  s.set(STORE_KEY, updated);

  stopWatcher(folderPath);

  return updated;
}

export async function getWatchedFolders(): Promise<WatchedFolderConfig[]> {
  const s = await getStore();
  return s.get(STORE_KEY, []);
}

export async function getWatcherStatus(): Promise<
  { path: string; active: boolean; watching: boolean }[]
> {
  const s = await getStore();
  const folders: WatchedFolderConfig[] = s.get(STORE_KEY, []);
  return folders.map((f: WatchedFolderConfig) => ({
    path: f.path,
    active: f.active,
    watching: watchers.has(f.path),
  }));
}

export async function pauseWatcher(): Promise<void> {
  for (const [, entry] of watchers) {
    if (entry.watcher) {
      await entry.watcher.close();
      entry.watcher = null;
    }
  }
}

export async function resumeWatcher(): Promise<void> {
  for (const [folderPath, entry] of watchers) {
    if (!entry.watcher && entry.config.active) {
      startWatcher(entry.config);
    }
  }
}

export async function registerFolderWatcher(): Promise<void> {
  const s = await getStore();
  const folders: WatchedFolderConfig[] = s.get(STORE_KEY, []);

  for (const config of folders) {
    if (config.active && fs.existsSync(config.path)) {
      startWatcher(config);
    }
  }
}

export async function unregisterFolderWatcher(): Promise<void> {
  for (const [folderPath] of watchers) {
    stopWatcher(folderPath);
  }
  watchers.clear();
}
