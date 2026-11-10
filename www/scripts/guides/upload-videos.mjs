/**
 * Uploads the captured guide videos to the site's Vercel Blob store and records
 * each one in `features/guides/guide-videos.json`, which the guide pages read.
 *
 * A video's address carries a hash of its bytes, so a new take gets a new
 * address and every take can be cached for a year; the take it replaces is
 * deleted from the store. Needs the store's `BLOB_READ_WRITE_TOKEN`. From `www`:
 *
 *   node scripts/guides/upload-videos.mjs             every video in the capture folder
 *   node scripts/guides/upload-videos.mjs set-up ...  only these
 */

import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { del, put } from "@vercel/blob";

const REPO = fileURLToPath(new URL("../../../", import.meta.url));
const VIDEOS = join(process.env.GUIDES_CAPTURE_DIR || join(REPO, ".capture"), "videos");
const MANIFEST = join(REPO, "www", "features", "guides", "guide-videos.json");
const A_YEAR = 365 * 24 * 60 * 60;

const token = process.env.BLOB_READ_WRITE_TOKEN;
if (!token) throw new Error("Set BLOB_READ_WRITE_TOKEN to the guides store's read-write token");

const wanted = process.argv.slice(2);
const slugs = (
	wanted.length
		? wanted
		: readdirSync(VIDEOS)
				.filter((name) => name.endsWith(".mp4"))
				.map((name) => name.slice(0, -4))
).sort();
const manifest = JSON.parse(readFileSync(MANIFEST, "utf8"));

for (const slug of slugs) {
	const file = join(VIDEOS, `${slug}.mp4`);
	if (!existsSync(file)) throw new Error(`No video for ${slug} in ${VIDEOS}`);
	const bytes = readFileSync(file);
	const pathname = `guides/${slug}-${createHash("sha256").update(bytes).digest("hex").slice(0, 12)}.mp4`;
	const previous = manifest.videos[slug];
	if (previous?.src.endsWith(`/${pathname}`)) continue;

	const { seconds } = JSON.parse(readFileSync(join(VIDEOS, `${slug}.json`), "utf8"));
	const blob = await put(pathname, bytes, {
		access: "public",
		contentType: "video/mp4",
		addRandomSuffix: false,
		cacheControlMaxAge: A_YEAR,
		token,
	});
	manifest.videos[slug] = { src: blob.url, seconds: Math.round(seconds) };
	if (previous) await del(previous.src, { token });
	console.log(`[guides] ${slug}: ${blob.url}`);
}

manifest.videos = Object.fromEntries(
	Object.entries(manifest.videos).sort(([a], [b]) => a.localeCompare(b))
);
writeFileSync(MANIFEST, `${JSON.stringify(manifest, null, "\t")}\n`);
