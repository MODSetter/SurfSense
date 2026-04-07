const STORE_KEY = 'activeSearchSpaceId';
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let store: any = null;

async function getStore() {
  if (!store) {
    const { default: Store } = await import('electron-store');
    store = new Store({
      name: 'active-search-space',
      defaults: { [STORE_KEY]: null as string | null },
    });
  }
  return store;
}

export async function getActiveSearchSpaceId(): Promise<string | null> {
  const s = await getStore();
  return (s.get(STORE_KEY) as string | null) ?? null;
}

export async function setActiveSearchSpaceId(id: string): Promise<void> {
  const s = await getStore();
  s.set(STORE_KEY, id);
}
