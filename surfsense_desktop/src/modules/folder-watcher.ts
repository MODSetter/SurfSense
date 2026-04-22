import { BrowserWindow, dialog } from 'electron';
import chokidar, { type FSWatcher } from 'chokidar';
import { randomUUID } from 'crypto';
import * as path from 'path';
import * as fs from 'fs';
import { IPC_CHANNELS } from '../ipc/channels';
import { trackEvent } from './analytics';

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
type FolderSyncAction = 'add' | 'change' | 'unlink';

export interface FolderSyncFileChangedEvent {
  id: string;
  rootFolderId: number | null;
  searchSpaceId: number;
  folderPath: string;
  folderName: string;
  relativePath: string;
  fullPath: string;
  action: FolderSyncAction;
  timestamp: number;
}

const STORE_KEY = 'watchedFolders';
const OUTBOX_STORE_KEY = 'events';
const MTIME_TOLERANCE_S = 1.0;

let store: any = null;
let mtimeStore: any = null;
let outboxStore: any = null;
let watchers: Map<string, WatcherEntry> = new Map();

/**
 * In-memory cache of mtime maps, keyed by folder path.
 * Persisted to electron-store on mutation.
 */
const mtimeMaps: Map<string, MtimeMap> = new Map();

let rendererReady = false;
const outboxEvents: Map<string, FolderSyncFileChangedEvent> = new Map();
let outboxLoaded = false;

export function markRendererReady() {
  rendererReady = true;
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

async function getOutboxStore() {
  if (!outboxStore) {
    const { default: Store } = await import('electron-store');
    outboxStore = new Store({
      name: 'folder-sync-outbox',
      defaults: {
        [OUTBOX_STORE_KEY]: [] as FolderSyncFileChangedEvent[],
      },
    });
  }
  return outboxStore;
}

function makeEventKey(event: Pick<FolderSyncFileChangedEvent, 'folderPath' | 'relativePath'>): string {
  return `${event.folderPath}:${event.relativePath}`;
}

function persistOutbox() {
  getOutboxStore().then((s) => {
    s.set(OUTBOX_STORE_KEY, Array.from(outboxEvents.values()));
  });
}

async function loadOutbox() {
  if (outboxLoaded) return;
  const s = await getOutboxStore();
  const stored: FolderSyncFileChangedEvent[] = s.get(OUTBOX_STORE_KEY, []);
  outboxEvents.clear();
  for (const event of stored) {
    if (!event?.id || !event.folderPath || !event.relativePath) continue;
    outboxEvents.set(makeEventKey(event), event);
  }
  outboxLoaded = true;
}

function sendFileChangedEvent(
  data: Omit<FolderSyncFileChangedEvent, 'id'>
) {
  const event: FolderSyncFileChangedEvent = {
    id: randomUUID(),
    ...data,
  };

  outboxEvents.set(makeEventKey(event), event);
  persistOutbox();

  if (rendererReady) {
    sendToRenderer(IPC_CHANNELS.FOLDER_SYNC_FILE_CHANGED, event);
  }
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

export interface FolderFileEntry {
  relativePath: string;
  fullPath: string;
  size: number;
  mtimeMs: number;
}

export function listFolderFiles(config: WatchedFolderConfig): FolderFileEntry[] {
  const root = config.path;
  const mtimeMap = walkFolderMtimes(config);
  const entries: FolderFileEntry[] = [];

  for (const [relativePath, mtimeMs] of Object.entries(mtimeMap)) {
    const fullPath = path.join(root, relativePath);
    try {
      const stat = fs.statSync(fullPath);
      entries.push({ relativePath, fullPath, size: stat.size, mtimeMs });
    } catch {
      // File may have been removed between walk and stat
    }
  }

  return entries;
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

  const handleFileEvent = (filePath: string, action: FolderSyncAction) => {
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

  trackEvent('desktop_folder_watch_added', {
    search_space_id: config.searchSpaceId,
    root_folder_id: config.rootFolderId,
    active: config.active,
    has_exclude_patterns: (config.excludePatterns?.length ?? 0) > 0,
    has_extension_filter: !!config.fileExtensions && config.fileExtensions.length > 0,
    is_update: existing >= 0,
  });

  return folders;
}

export async function removeWatchedFolder(
  folderPath: string
): Promise<WatchedFolderConfig[]> {
  const s = await getStore();
  const folders: WatchedFolderConfig[] = s.get(STORE_KEY, []);
  const removed = folders.find((f: WatchedFolderConfig) => f.path === folderPath);
  const updated = folders.filter((f: WatchedFolderConfig) => f.path !== folderPath);
  s.set(STORE_KEY, updated);

  stopWatcher(folderPath);

  mtimeMaps.delete(folderPath);
  const ms = await getMtimeStore();
  ms.delete(folderPath);

  if (removed) {
    trackEvent('desktop_folder_watch_removed', {
      search_space_id: removed.searchSpaceId,
      root_folder_id: removed.rootFolderId,
    });
  }

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

export async function getPendingFileEvents(): Promise<FolderSyncFileChangedEvent[]> {
  await loadOutbox();
  return Array.from(outboxEvents.values()).sort((a, b) => a.timestamp - b.timestamp);
}

export async function acknowledgeFileEvents(eventIds: string[]): Promise<{ acknowledged: number }> {
  if (!eventIds || eventIds.length === 0) return { acknowledged: 0 };
  await loadOutbox();

  const ackSet = new Set(eventIds);
  let acknowledged = 0;
  const foldersToUpdate = new Set<string>();

  for (const [key, event] of outboxEvents.entries()) {
    if (ackSet.has(event.id)) {
      if (event.action !== 'unlink') {
        const map = mtimeMaps.get(event.folderPath);
        if (map) {
          try {
            map[event.relativePath] = fs.statSync(event.fullPath).mtimeMs;
            foldersToUpdate.add(event.folderPath);
          } catch {
            // File may have been removed
          }
        }
      }
      outboxEvents.delete(key);
      acknowledged += 1;
    }
  }

  for (const fp of foldersToUpdate) {
    persistMtimeMap(fp);
  }

  if (acknowledged > 0) {
    persistOutbox();
  }

  return { acknowledged };
}

export async function seedFolderMtimes(
  folderPath: string,
  mtimes: Record<string, number>,
): Promise<void> {
  const ms = await getMtimeStore();
  const existing: MtimeMap = ms.get(folderPath) ?? {};
  const merged = { ...existing, ...mtimes };
  mtimeMaps.set(folderPath, merged);
  ms.set(folderPath, merged);
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
  await loadOutbox();
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

export async function browseFiles(): Promise<string[] | null> {
  const result = await dialog.showOpenDialog({
    properties: ['openFile', 'multiSelections'],
    title: 'Select files',
  });
  if (result.canceled || result.filePaths.length === 0) return null;
  return result.filePaths;
}

const MIME_MAP: Record<string, string> = {
  '.pdf': 'application/pdf',
  '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  '.html': 'text/html', '.htm': 'text/html',
  '.csv': 'text/csv',
  '.txt': 'text/plain',
  '.md': 'text/markdown', '.markdown': 'text/markdown',
  '.mp3': 'audio/mpeg', '.mpeg': 'audio/mpeg', '.mpga': 'audio/mpeg',
  '.mp4': 'audio/mp4', '.m4a': 'audio/mp4',
  '.wav': 'audio/wav',
  '.webm': 'audio/webm',
  '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.png': 'image/png',
  '.bmp': 'image/bmp',
  '.webp': 'image/webp',
  '.tiff': 'image/tiff',
  '.doc': 'application/msword',
  '.rtf': 'application/rtf',
  '.xml': 'application/xml',
  '.epub': 'application/epub+zip',
  '.xls': 'application/vnd.ms-excel',
  '.ppt': 'application/vnd.ms-powerpoint',
  '.eml': 'message/rfc822',
  '.odt': 'application/vnd.oasis.opendocument.text',
  '.msg': 'application/vnd.ms-outlook',
};

export interface LocalFileData {
  name: string;
  data: ArrayBuffer;
  mimeType: string;
  size: number;
}

export function readLocalFiles(filePaths: string[]): LocalFileData[] {
  return filePaths.map((p) => {
    const buf = fs.readFileSync(p);
    const ext = path.extname(p).toLowerCase();
    return {
      name: path.basename(p),
      data: buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength),
      mimeType: MIME_MAP[ext] || 'application/octet-stream',
      size: buf.byteLength,
    };
  });
}
