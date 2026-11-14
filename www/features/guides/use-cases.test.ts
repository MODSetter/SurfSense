import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { mayAutoplay } from "./autoplay";
import { guidePoster } from "./guide-video-source";
import { findUseCase, USE_CASE_SLUGS } from "./use-cases";

// Run with: pnpm exec tsx --test features/guides/use-cases.test.ts

const GUIDES = path.join(__dirname, "../../content/docs/v2/guides");
const PUBLIC = path.join(__dirname, "../../public");

function guidePage(slug: string): string {
	const file = path.join(GUIDES, `${slug}.mdx`);
	assert.ok(existsSync(file), `${slug}: no guide at content/docs/v2/guides/${slug}.mdx`);
	return readFileSync(file, "utf8");
}

test("every use case shows its guide's own video, title and poster", () => {
	for (const slug of USE_CASE_SLUGS) {
		const { heading, title } = findUseCase(slug);
		const page = guidePage(slug);
		assert.equal(
			/^title: (.+)$/m.exec(page)?.[1],
			heading,
			`${slug}: heading is not the guide's title`
		);
		const video = /<GuideVideo\b([^>]*)\/>/.exec(page)?.[1] ?? "";
		assert.match(video, new RegExp(`slug="${slug}"`), `${slug}: the guide shows another video`);
		assert.equal(/title="([^"]+)"/.exec(video)?.[1], title, `${slug}: title is not the video's`);
		assert.ok(existsSync(path.join(PUBLIC, guidePoster(slug))), `${slug}: no poster in public/`);
	}
});

test("use-case steps are three short sentences in the docs' prose rules", () => {
	for (const slug of USE_CASE_SLUGS) {
		const { label, steps } = findUseCase(slug);
		assert.equal(steps.length, 3, `${slug}: a use case has three steps`);
		for (const text of [label, ...steps]) {
			assert.doesNotMatch(text, /[–—]| - /, `${slug}: no dashes in "${text}"`);
		}
		for (const step of steps) {
			assert.ok(step.length <= 100, `${slug}: "${step}" is too long for a basic guide`);
			assert.match(step, /[.!?”]$/, `${slug}: "${step}" is not a sentence`);
		}
	}
});

test("a video never plays by itself for a visitor who asked for less motion or less data", () => {
	assert.equal(mayAutoplay({ reducedMotion: false, saveData: false }), true);
	assert.equal(mayAutoplay({ reducedMotion: true, saveData: false }), false);
	assert.equal(mayAutoplay({ reducedMotion: false, saveData: true }), false);
});
