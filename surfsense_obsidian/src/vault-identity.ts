import type { App } from "obsidian";

/**
 * Deterministic SHA-256 over the vault name + sorted markdown paths.
 *
 * Two devices observing the same vault content compute the same value,
 * regardless of how it was synced (iCloud, Syncthing, Obsidian Sync, …).
 * The server uses this as the cross-device dedup key on /connect.
 */
export async function computeVaultFingerprint(app: App): Promise<string> {
	const vaultName = app.vault.getName();
	const paths = app.vault
		.getMarkdownFiles()
		.map((f) => f.path)
		.sort();
	const payload = `${vaultName}\n${paths.join("\n")}`;
	const bytes = new TextEncoder().encode(payload);
	const digest = await crypto.subtle.digest("SHA-256", bytes);
	return bufferToHex(digest);
}

function bufferToHex(buf: ArrayBuffer): string {
	const view = new Uint8Array(buf);
	let hex = "";
	for (let i = 0; i < view.length; i++) {
		hex += (view[i] ?? 0).toString(16).padStart(2, "0");
	}
	return hex;
}

export function generateVaultUuid(): string {
	const c = globalThis.crypto;
	if (c?.randomUUID) return c.randomUUID();
	const buf = new Uint8Array(16);
	c.getRandomValues(buf);
	buf[6] = ((buf[6] ?? 0) & 0x0f) | 0x40;
	buf[8] = ((buf[8] ?? 0) & 0x3f) | 0x80;
	const hex = Array.from(buf, (b) => b.toString(16).padStart(2, "0")).join("");
	return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(
		16,
		20,
	)}-${hex.slice(20)}`;
}
