export interface ShortcutConfig {
  generalAssist: string;
  quickAsk: string;
  screenshotAssist: string;
}

const DEFAULTS: ShortcutConfig = {
  generalAssist: 'CommandOrControl+Shift+S',
  quickAsk: 'CommandOrControl+Alt+S',
  screenshotAssist: 'CommandOrControl+Shift+Space',
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
  const raw = (s.get(STORE_KEY) as Record<string, string> | undefined) ?? {};
  const legacyAutocomplete = raw.autocomplete;
  const { autocomplete: _drop, ...rest } = raw;
  let merged: ShortcutConfig = { ...DEFAULTS, ...rest };
  if (
    typeof legacyAutocomplete === 'string' &&
    legacyAutocomplete.length > 0 &&
    !('screenshotAssist' in raw)
  ) {
    merged = { ...merged, screenshotAssist: legacyAutocomplete };
    s.set(STORE_KEY, {
      generalAssist: merged.generalAssist,
      quickAsk: merged.quickAsk,
      screenshotAssist: merged.screenshotAssist,
    });
  }
  return merged;
}

export async function setShortcuts(config: Partial<ShortcutConfig>): Promise<ShortcutConfig> {
  const s = await getStore();
  const raw = (s.get(STORE_KEY) as Record<string, string> | undefined) ?? {};
  const { autocomplete: _drop, ...current } = raw;
  const merged = { ...DEFAULTS, ...current, ...config };
  s.set(STORE_KEY, merged);
  return merged;
}

export function getDefaults(): ShortcutConfig {
  return { ...DEFAULTS };
}
