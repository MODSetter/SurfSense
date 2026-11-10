/**
 * Puts the guides' public demo documents in a local folder, each checked
 * against the sha256 in `manifest.json`, so every capture reads the same bytes.
 * A file already there with the right hash is not fetched again.
 */

import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

const MANIFEST = new URL("./manifest.json", import.meta.url);

function sha256(bytes) {
	return createHash("sha256").update(bytes).digest("hex");
}

/** @returns {Promise<string>} the folder holding the documents */
export async function fetchDemoDocuments(folder) {
	const { documents } = JSON.parse(readFileSync(MANIFEST, "utf8"));
	for (const document of documents) {
		const path = join(folder, document.file);
		if (existsSync(path) && sha256(readFileSync(path)) === document.sha256) continue;
		const response = await fetch(document.url, { redirect: "follow" });
		if (!response.ok) throw new Error(`${document.url} answered ${response.status}`);
		const bytes = Buffer.from(await response.arrayBuffer());
		const got = sha256(bytes);
		if (got !== document.sha256) {
			throw new Error(
				`${document.file} changed at its source (sha256 ${got}); check it and update the manifest`
			);
		}
		mkdirSync(dirname(path), { recursive: true });
		writeFileSync(path, bytes);
	}
	return folder;
}
