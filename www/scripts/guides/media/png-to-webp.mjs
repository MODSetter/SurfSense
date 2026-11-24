/**
 * A screenshot as the site serves it: lossy WebP at a quality where interface
 * text stays sharp at 2×, which keeps a full-window shot near 100 KB rather
 * than the PNG's 400 KB or more.
 */

import { runFfmpeg } from "./run-ffmpeg.mjs";

// A busy background, such as the welcome screen's dithered one, takes a lower quality to stay in budget.
export function pngToWebp(png, webp, quality = 90) {
	return runFfmpeg([
		"-i",
		png,
		"-c:v",
		"libwebp",
		"-quality",
		String(quality),
		"-compression_level",
		"6",
		"-preset",
		"drawing",
		webp,
	]);
}
