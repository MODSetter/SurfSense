export interface ShortcutConfig {
  generalAssist: string;
  quickAsk: string;
  autocomplete: string;
}

const DEFAULTS: ShortcutConfig = {
  generalAssist: 'CommandOrControl+Shift+S',
  quickAsk: 'CommandOrControl+Alt+S',
  autocomplete: 'CommandOrControl+Shift+Space',
};

const STORE_KEY = 'shortcuts';
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- lazily imported ESM module; matches folder-watcher.ts pattern
let store: any = null;

async function getStore() {
  if (!store) {
    const { default: Store } = await import('electron-store');
    store = new Store({
      name: 'keyboard-shortcuts',
      defaults: { [STORE_KEY]: DEFAULTS },
    });
  }
  return store;
}

export async function getShortcuts(): Promise<ShortcutConfig> {
  const s = await getStore();
  const stored = s.get(STORE_KEY) as Partial<ShortcutConfig> | undefined;
  return { ...DEFAULTS, ...stored };
}

export async function setShortcuts(config: Partial<ShortcutConfig>): Promise<ShortcutConfig> {
  const s = await getStore();
  const current = (s.get(STORE_KEY) as ShortcutConfig) ?? DEFAULTS;
  const merged = { ...current, ...config };
  s.set(STORE_KEY, merged);
  return merged;
}

export function getDefaults(): ShortcutConfig {
  return { ...DEFAULTS };
}
