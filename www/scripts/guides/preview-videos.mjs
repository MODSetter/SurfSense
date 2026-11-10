/**
 * Lets `next dev` play the captured guide videos before they are uploaded: copies
 * them into `public/guide-videos-local/`, which git ignores. GuideVideo plays a
 * guide's uploaded video when there is one, and in development falls back to
 * these. A build never does. From `www`:
 *
 *   node scripts/guides/preview-videos.mjs
 */

import { copyFileSync, mkdirSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = fileURLToPath(new URL("../../../", import.meta.url));
const VIDEOS = join(process.env.GUIDES_CAPTURE_DIR || join(REPO, ".capture"), "videos");
const LOCAL = join(REPO, "www", "public", "guide-videos-local");

mkdirSync(LOCAL, { recursive: true });
const takes = readdirSync(VIDEOS).filter((name) => name.endsWith(".mp4"));
for (const name of takes) copyFileSync(join(VIDEOS, name), join(LOCAL, name));
console.log(`[guides] ${takes.length} videos ready for next dev in public/guide-videos-local/`);
