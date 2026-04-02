import { BrowserWindow, dialog } from 'electron';
import chokidar, { type FSWatcher } from 'chokidar';
import * as path from 'path';
import * as fs from 'fs';
import { IPC_CHANNELS } from '../ipc/channels';

export interface WatchedFolderConfig {
  path: string;
  name: string;
  excludePatterns: string[];
  fileExtensions: string[] | null;
  rootFolderId: number | null;
  searchSpaceId: number;
  active: boolean;
}

interface WatcherEntry {
  config: WatchedFolderConfig;
  watcher: FSWatcher | null;
}

type MtimeMap = Record<string, number>;

const STORE_KEY = 'watchedFolders';
const MTIME_TOLERANCE_S = 1.0;

let store: any = null;
let mtimeStore: any = null;
let watchers: Map<string, WatcherEntry> = new Map();

/**
 * In-memory cache of mtime maps, keyed by folder path.
 * Persisted to electron-store on mutation.
 */
const mtimeMaps: Map<string, MtimeMap> = new Map();

let rendererReady = false;
const pendingEvents: any[] = [];

export function markRendererReady() {
  rendererReady = true;
  for (const event of pendingEvents) {
    sendToRenderer(IPC_CHANNELS.FOLDER_SYNC_FILE_CHANGED, event);
  }
  pendingEvents.length = 0;
}

function sendFileChangedEvent(data: any) {
  if (rendererReady) {
    sendToRenderer(IPC_CHANNELS.FOLDER_SYNC_FILE_CHANGED, data);
  } else {
    pendingEvents.push(data);
  }
}

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

async function getMtimeStore() {
  if (!mtimeStore) {
    const { default: Store } = await import('electron-store');
    mtimeStore = new Store({
      name: 'folder-mtime-maps',
      defaults: {} as Record<string, MtimeMap>,
    });
  }
  return mtimeStore;
}

function loadMtimeMap(folderPath: string): MtimeMap {
  return mtimeMaps.get(folderPath) ?? {};
}

function persistMtimeMap(folderPath: string) {
  const map = mtimeMaps.get(folderPath) ?? {};
  getMtimeStore().then((s) => s.set(folderPath, map));
}

function walkFolderMtimes(config: WatchedFolderConfig): MtimeMap {
  const root = config.path;
  const result: MtimeMap = {};
  const excludes = new Set(config.excludePatterns);

  function walk(dir: string) {
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }

    for (const entry of entries) {
      const name = entry.name;

      if (name.startsWith('.') || excludes.has(name)) continue;

      const full = path.join(dir, name);

      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile()) {
        if (
          config.fileExtensions &&
          config.fileExtensions.length > 0
        ) {
          const ext = path.extname(name).toLowerCase();
          if (!config.fileExtensions.includes(ext)) continue;
        }

        try {
          const stat = fs.statSync(full);
          const rel = path.relative(root, full);
          result[rel] = stat.mtimeMs;
        } catch {
          // File may have been removed between readdir and stat
        }
      }
    }
  }

  walk(root);
  return result;
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

async function startWatcher(config: WatchedFolderConfig) {
  if (watchers.has(config.path)) {
    return;
  }

  const ms = await getMtimeStore();
  const storedMap: MtimeMap = ms.get(config.path) ?? {};
  mtimeMaps.set(config.path, { ...storedMap });

  const ignored = [
    /(^|[/\\])\../, // dotfiles by default
    ...config.excludePatterns.map((p) => `**/${p}/**`),
  ];

  const watcher = chokidar.watch(config.path, {
    persistent: true,
    ignoreInitial: true,
    awaitWriteFinish: {
      stabilityThreshold: 500,
      pollInterval: 100,
    },
    ignored,
  });

  let ready = false;

  watcher.on('ready', () => {
    ready = true;

    const currentMap = walkFolderMtimes(config);
    const storedSnapshot = loadMtimeMap(config.path);
    const now = Date.now();

    // Track which files are unchanged so we can selectively update the mtime map
    const unchangedMap: MtimeMap = {};

    for (const [rel, currentMtime] of Object.entries(currentMap)) {
      const storedMtime = storedSnapshot[rel];
      if (storedMtime === undefined) {
        sendFileChangedEvent({
          rootFolderId: config.rootFolderId,
          searchSpaceId: config.searchSpaceId,
          folderPath: config.path,
          folderName: config.name,
          relativePath: rel,
          fullPath: path.join(config.path, rel),
          action: 'add',
          timestamp: now,
        });
      } else if (Math.abs(currentMtime - storedMtime) >= MTIME_TOLERANCE_S * 1000) {
        sendFileChangedEvent({
          rootFolderId: config.rootFolderId,
          searchSpaceId: config.searchSpaceId,
          folderPath: config.path,
          folderName: config.name,
          relativePath: rel,
          fullPath: path.join(config.path, rel),
          action: 'change',
          timestamp: now,
        });
      } else {
        unchangedMap[rel] = currentMtime;
      }
    }

    for (const rel of Object.keys(storedSnapshot)) {
      if (!(rel in currentMap)) {
        sendFileChangedEvent({
          rootFolderId: config.rootFolderId,
          searchSpaceId: config.searchSpaceId,
          folderPath: config.path,
          folderName: config.name,
          relativePath: rel,
          fullPath: path.join(config.path, rel),
          action: 'unlink',
          timestamp: now,
        });
      }
    }

    // Only update the mtime map for unchanged files; changed files keep their
    // stored mtime so they'll be re-detected if the app crashes before indexing.
    mtimeMaps.set(config.path, unchangedMap);
    persistMtimeMap(config.path);

    sendToRenderer(IPC_CHANNELS.FOLDER_SYNC_WATCHER_READY, {
      rootFolderId: config.rootFolderId,
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

    const map = mtimeMaps.get(config.path);
    if (map) {
      if (action === 'unlink') {
        delete map[relativePath];
      } else {
        try {
          map[relativePath] = fs.statSync(filePath).mtimeMs;
        } catch {
          // File may have been removed between event and stat
        }
      }
      persistMtimeMap(config.path);
    }

    sendFileChangedEvent({
      rootFolderId: config.rootFolderId,
      searchSpaceId: config.searchSpaceId,
      folderPath: config.path,
      folderName: config.name,
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
  persistMtimeMap(folderPath);
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
    await startWatcher(config);
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

  mtimeMaps.delete(folderPath);
  const ms = await getMtimeStore();
  ms.delete(folderPath);

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
  for (const [, entry] of watchers) {
    if (!entry.watcher && entry.config.active) {
      await startWatcher(entry.config);
    }
  }
}

export async function registerFolderWatcher(): Promise<void> {
  const s = await getStore();
  const folders: WatchedFolderConfig[] = s.get(STORE_KEY, []);

  for (const config of folders) {
    if (config.active && fs.existsSync(config.path)) {
      await startWatcher(config);
    }
  }
}

export async function unregisterFolderWatcher(): Promise<void> {
  for (const [folderPath] of watchers) {
    stopWatcher(folderPath);
  }
  watchers.clear();
}
