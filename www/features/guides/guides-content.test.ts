import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import guideVideos from "./guide-videos.json";

// Run with: pnpm exec tsx --test features/guides/guides-content.test.ts

const GUIDES = path.join(__dirname, "../../content/docs/v2/guides");
const PUBLIC = path.join(__dirname, "../../public");
const PUBLIC_GUIDES = path.join(PUBLIC, "guides");
// A shot is captured at 2× and saved as lossy WebP; past this, it is too busy or too big.
const MAX_SHOT_BYTES = 250 * 1024;
const VIDEO_HOST = /\.public\.blob\.vercel-storage\.com$/;

const VIDEOS: Record<string, { src: string; seconds: number }> = guideVideos.videos;

function pages(): { file: string; text: string }[] {
	return readdirSync(GUIDES)
		.filter((name) => name.endsWith(".mdx"))
		.map((name) => ({ file: name, text: readFileSync(path.join(GUIDES, name), "utf8") }));
}

function images(text: string): { alt: string; src: string }[] {
	return [...text.matchAll(/!\[([^\]]*)\]\((\/guides\/[^)\s]+)\)/g)].map(([, alt, src]) => ({
		alt,
		src,
	}));
}

function videoTags(text: string): { slug: string; poster: string }[] {
	return [...text.matchAll(/<GuideVideo\b([^>]*)\/>/g)].map(([, props]) => ({
		slug: /slug="([^"]+)"/.exec(props)?.[1] ?? "",
		poster: /poster="([^"]+)"/.exec(props)?.[1] ?? "",
	}));
}

function filesUnder(dir: string): string[] {
	if (!existsSync(dir)) return [];
	return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
		const full = path.join(dir, entry.name);
		return entry.isDirectory() ? filesUnder(full) : [full];
	});
}

test("every screenshot a guide shows exists, has alt text and stays small", () => {
	for (const { file, text } of pages()) {
		for (const { alt, src } of images(text)) {
			assert.ok(alt.trim(), `${file}: ${src} has no alt text`);
			const onDisk = path.join(PUBLIC, src);
			assert.ok(existsSync(onDisk), `${file}: ${src} is not in public/`);
			assert.ok(
				statSync(onDisk).size <= MAX_SHOT_BYTES,
				`${file}: ${src} is over ${MAX_SHOT_BYTES} bytes`
			);
		}
	}
});

test("every guide video is hosted, and its poster is in public/", () => {
	for (const { file, text } of pages()) {
		for (const { slug, poster } of videoTags(text)) {
			const video = VIDEOS[slug];
			assert.ok(video, `${file}: no video uploaded for ${slug}`);
			assert.match(
				new URL(video.src).hostname,
				VIDEO_HOST,
				`${file}: ${slug} is not on the Blob store`
			);
			assert.ok(video.seconds > 0, `${file}: ${slug} has no length`);
			assert.ok(
				existsSync(path.join(PUBLIC, poster)),
				`${file}: poster ${poster} is not in public/`
			);
		}
	}
});

test("no picture under public/guides is left behind by a renamed or dropped step", () => {
	const shown = new Set(
		pages().flatMap(({ text }) => [
			...images(text).map((image) => image.src),
			...videoTags(text).map((tag) => tag.poster),
		])
	);
	for (const file of filesUnder(PUBLIC_GUIDES)) {
		const src = `/${path.relative(PUBLIC, file).replaceAll(path.sep, "/")}`;
		assert.ok(shown.has(src), `${src} is on no guide page`);
	}
});
