/**
 * One-time read-migration for persisted watched-folder configs: legacy configs
 * stored the workspace as `searchSpaceId`. Map it to `workspaceId` so existing
 * watched folders keep their sync target after the rename. Pure + dependency-free
 * so it can be unit-checked without loading electron-store.
 *
 * Returns the migrated configs and whether anything changed (so callers can
 * write back only when needed).
 */
export function migrateWatchedFolderConfigs<T>(
  raw: Array<Record<string, unknown>>
): { configs: T[]; migrated: boolean } {
  let migrated = false;
  const configs = raw.map((c) => {
    if (c.workspaceId === undefined && c.searchSpaceId !== undefined) {
      migrated = true;
      const { searchSpaceId, ...rest } = c;
      return { ...rest, workspaceId: searchSpaceId } as unknown as T;
    }
    return c as unknown as T;
  });
  return { configs, migrated };
}
