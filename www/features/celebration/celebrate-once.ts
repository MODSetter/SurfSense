type FlagStorage = Pick<Storage, "getItem" | "setItem">;

const PREFIX = "surfsense:celebrated:";

// Reached inside each call, since merely reading `window.localStorage` throws
// where site data is blocked; `celebrateOnce` catches it there.
export const browserFlags: FlagStorage = {
	getItem: (key) => window.localStorage.getItem(key),
	setItem: (key, value) => window.localStorage.setItem(key, value),
};

/**
 * Fires at most once per key in this browser, so a reload or a second download
 * of the same checkout does not celebrate again. Storage a browser refuses
 * (private windows, blocked site data) only loses the memory, never the page.
 */
export function celebrateOnce(
	key: string,
	{ storage, fire }: { storage: FlagStorage; fire: () => void }
): void {
	try {
		if (storage.getItem(PREFIX + key) !== null) return;
		storage.setItem(PREFIX + key, "1");
	} catch {
		// No memory to consult: celebrating twice beats never celebrating.
	}
	fire();
}
