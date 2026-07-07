const STORE_KEY = 'activeWorkspaceId';
let store: any = null;

async function getStore() {
  if (!store) {
    const { default: Store } = await import('electron-store');
    store = new Store({
      name: 'active-workspace',
      defaults: { [STORE_KEY]: null as string | null },
    });
    // One-time migration from the legacy `active-search-space` store so the
    // user's last-selected workspace survives the rename.
    if (store.get(STORE_KEY) == null) {
      const legacy: any = new Store({
        name: 'active-search-space',
        defaults: { activeSearchSpaceId: null as string | null },
      });
      const prev = legacy.get('activeSearchSpaceId') as string | null;
      if (prev != null) store.set(STORE_KEY, prev);
    }
  }
  return store;
}

export async function getActiveWorkspaceId(): Promise<string | null> {
  const s = await getStore();
  return (s.get(STORE_KEY) as string | null) ?? null;
}

export async function setActiveWorkspaceId(id: string): Promise<void> {
  const s = await getStore();
  s.set(STORE_KEY, id);
}
