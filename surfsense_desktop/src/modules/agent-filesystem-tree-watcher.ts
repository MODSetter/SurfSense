import { BrowserWindow } from 'electron';
import chokidar, { type FSWatcher } from 'chokidar';
import { resolve } from 'node:path';
import { IPC_CHANNELS } from '../ipc/channels';
import { listAgentFilesystemFiles } from './agent-filesystem';

const SAFETY_POLL_MS = 60_000;
const EVENT_DEBOUNCE_MS = 700;

export type AgentFilesystemTreeWatchOptions = {
  workspaceId?: number | null;
  rootPaths: string[];
  excludePatterns?: string[] | null;
  fileExtensions?: string[] | null;
};

type TreeDirtyReason = 'watcher_event' | 'safety_poll';

type TreeDirtyEvent = {
  workspaceId: number | null;
  reason: TreeDirtyReason;
  rootPath: string;
  changedPath: string | null;
  timestamp: number;
};

type WatchSession = {
  workspaceId: number | null;
  optionsSignature: string;
  rootPaths: string[];
  excludePatterns: string[];
  fileExtensions: string[] | null;
  watchers: FSWatcher[];
  pollTimer: NodeJS.Timeout | null;
  emitTimer: NodeJS.Timeout | null;
  rootSnapshotByPath: Map<string, string>;
  pendingDirtyByRoot: Map<string, { reason: TreeDirtyReason; changedPath: string | null }>;
  disposed: boolean;
};

const sessions = new Map<string, WatchSession>();

function normalizeWorkspaceId(workspaceId?: number | null): number | null {
  if (typeof workspaceId === 'number' && Number.isFinite(workspaceId) && workspaceId > 0) {
    return workspaceId;
  }
  return null;
}

function getSessionKey(workspaceId?: number | null): string {
  const normalized = normalizeWorkspaceId(workspaceId);
  return normalized === null ? 'default' : String(normalized);
}

function normalizeRootPath(pathValue: string): string {
  const normalized = resolve(pathValue.trim());
  return process.platform === 'win32' ? normalized.toLowerCase() : normalized;
}

function normalizeList(value: string[] | null | undefined): string[] {
  if (!value || value.length === 0) return [];
  return value
    .filter((entry): entry is string => typeof entry === 'string')
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function normalizeExtensions(value: string[] | null | undefined): string[] | null {
  const normalized = normalizeList(value).map((entry) => entry.toLowerCase());
  return normalized.length > 0 ? normalized : null;
}

function buildOptionsSignature(
  workspaceId: number | null,
  rootPaths: string[],
  excludePatterns: string[],
  fileExtensions: string[] | null
): string {
  return JSON.stringify({
    workspaceId,
    rootPaths: [...rootPaths].sort(),
    excludePatterns: [...excludePatterns].sort(),
    fileExtensions: fileExtensions ? [...fileExtensions].sort() : null,
  });
}

function hashText(input: string, seed: number): number {
  let hash = seed >>> 0;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
    hash >>>= 0;
  }
  return hash;
}

async function buildRootSnapshotSignature(
  session: WatchSession,
  rootPath: string
): Promise<string> {
  let hash = 2166136261;
  hash = hashText(`space:${session.workspaceId ?? 'default'}|root:${rootPath}`, hash);
  const files = await listAgentFilesystemFiles({
    rootPath,
    workspaceId: session.workspaceId,
    excludePatterns: session.excludePatterns,
    fileExtensions: session.fileExtensions,
  });
  const sortedFiles = [...files].sort((a, b) => a.relativePath.localeCompare(b.relativePath));
  hash = hashText(`count:${sortedFiles.length}`, hash);
  for (const file of sortedFiles) {
    hash = hashText(
      `${file.relativePath}|${Math.round(file.mtimeMs)}|${file.size}`,
      hash
    );
  }
  return hash.toString(16);
}

function sendTreeDirtyEvent(
  workspaceId: number | null,
  reason: TreeDirtyReason,
  rootPath: string,
  changedPath: string | null
): void {
  const payload: TreeDirtyEvent = {
    workspaceId,
    reason,
    rootPath,
    changedPath,
    timestamp: Date.now(),
  };
  for (const win of BrowserWindow.getAllWindows()) {
    if (!win.isDestroyed()) {
      win.webContents.send(IPC_CHANNELS.AGENT_FILESYSTEM_TREE_DIRTY, payload);
    }
  }
}

function scheduleDirtyEmit(
  session: WatchSession,
  reason: TreeDirtyReason,
  rootPath: string,
  changedPath: string | null = null
): void {
  if (session.disposed) return;
  const existing = session.pendingDirtyByRoot.get(rootPath);
  if (!existing || existing.reason === 'safety_poll') {
    session.pendingDirtyByRoot.set(rootPath, { reason, changedPath });
  }
  if (session.emitTimer) {
    clearTimeout(session.emitTimer);
  }
  session.emitTimer = setTimeout(() => {
    session.emitTimer = null;
    if (session.disposed) return;
    const pending = Array.from(session.pendingDirtyByRoot.entries());
    session.pendingDirtyByRoot.clear();
    for (const [pendingRootPath, payload] of pending) {
      sendTreeDirtyEvent(
        session.workspaceId,
        payload.reason,
        pendingRootPath,
        payload.changedPath
      );
    }
  }, EVENT_DEBOUNCE_MS);
}

async function closeSession(session: WatchSession): Promise<void> {
  session.disposed = true;
  if (session.emitTimer) {
    clearTimeout(session.emitTimer);
    session.emitTimer = null;
  }
  if (session.pollTimer) {
    clearInterval(session.pollTimer);
    session.pollTimer = null;
  }
  await Promise.allSettled(session.watchers.map((watcher) => watcher.close()));
}

export async function startAgentFilesystemTreeWatch(
  options: AgentFilesystemTreeWatchOptions
): Promise<{ ok: true }> {
  const workspaceId = normalizeWorkspaceId(options.workspaceId);
  const rootPaths = Array.from(
    new Set(normalizeList(options.rootPaths).map((rootPath) => normalizeRootPath(rootPath)))
  );
  const excludePatterns = Array.from(new Set(normalizeList(options.excludePatterns)));
  const fileExtensions = normalizeExtensions(options.fileExtensions);
  const sessionKey = getSessionKey(workspaceId);

  if (rootPaths.length === 0) {
    await stopAgentFilesystemTreeWatch(workspaceId);
    return { ok: true };
  }

  const optionsSignature = buildOptionsSignature(
    workspaceId,
    rootPaths,
    excludePatterns,
    fileExtensions
  );
  const existing = sessions.get(sessionKey);
  if (existing && existing.optionsSignature === optionsSignature) {
    return { ok: true };
  }
  if (existing) {
    await closeSession(existing);
    sessions.delete(sessionKey);
  }

  const ignored = [
    /(^|[/\\])\../,
    ...excludePatterns.map((pattern) => `**/${pattern}/**`),
  ];
  const watchers = rootPaths.map((rootPath) =>
    chokidar.watch(rootPath, {
      persistent: true,
      ignoreInitial: true,
      awaitWriteFinish: {
        stabilityThreshold: 500,
        pollInterval: 100,
      },
      ignored,
    })
  );

  const session: WatchSession = {
    workspaceId,
    optionsSignature,
    rootPaths,
    excludePatterns,
    fileExtensions,
    watchers,
    pollTimer: null,
    emitTimer: null,
    rootSnapshotByPath: new Map(),
    pendingDirtyByRoot: new Map(),
    disposed: false,
  };

  for (let index = 0; index < watchers.length; index += 1) {
    const watcher = watchers[index];
    const rootPath = rootPaths[index];
    watcher.on('add', (filePath) => scheduleDirtyEmit(session, 'watcher_event', rootPath, filePath));
    watcher.on('change', (filePath) =>
      scheduleDirtyEmit(session, 'watcher_event', rootPath, filePath)
    );
    watcher.on('unlink', (filePath) =>
      scheduleDirtyEmit(session, 'watcher_event', rootPath, filePath)
    );
    watcher.on('addDir', (filePath) =>
      scheduleDirtyEmit(session, 'watcher_event', rootPath, filePath)
    );
    watcher.on('unlinkDir', (filePath) =>
      scheduleDirtyEmit(session, 'watcher_event', rootPath, filePath)
    );
  }

  for (const rootPath of rootPaths) {
    try {
      const signature = await buildRootSnapshotSignature(session, rootPath);
      session.rootSnapshotByPath.set(rootPath, signature);
    } catch {
      session.rootSnapshotByPath.set(rootPath, '');
    }
  }

  session.pollTimer = setInterval(() => {
    void (async () => {
      if (session.disposed) return;
      for (const rootPath of session.rootPaths) {
        try {
          const nextSignature = await buildRootSnapshotSignature(session, rootPath);
          const previousSignature = session.rootSnapshotByPath.get(rootPath) ?? '';
          if (nextSignature !== previousSignature) {
            session.rootSnapshotByPath.set(rootPath, nextSignature);
            scheduleDirtyEmit(session, 'safety_poll', rootPath, null);
          }
        } catch {
          // Keep watcher resilient on transient IO errors.
        }
      }
    })();
  }, SAFETY_POLL_MS);

  sessions.set(sessionKey, session);
  return { ok: true };
}

export async function stopAgentFilesystemTreeWatch(
  workspaceId?: number | null
): Promise<{ ok: true }> {
  const sessionKey = getSessionKey(workspaceId);
  const session = sessions.get(sessionKey);
  if (!session) return { ok: true };
  sessions.delete(sessionKey);
  await closeSession(session);
  return { ok: true };
}
