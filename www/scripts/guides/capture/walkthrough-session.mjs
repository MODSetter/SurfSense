/**
 * What a walkthrough script drives the app with. Each action moves the drawn
 * pointer first, so the video shows where it clicks, and every wait and
 * screenshot is timed, so the video editor can speed up the waits and cut out
 * the frames where the overlay was hidden for a screenshot.
 */

import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { pngToWebp } from "../media/png-to-webp.mjs";

const POINTER_TRAVEL_MS = 600;

/**
 * @param {{ page: import("@playwright/test").Page, slug: string, shotsDir: string,
 *   scratchDir: string, docsDir: string, startedAt: number }} options
 */
export function createWalkthroughSession({ page, slug, shotsDir, scratchDir, docsDir, startedAt }) {
	const marks = [];
	const shots = [];
	const seconds = () => (Date.now() - startedAt) / 1000;
	mkdirSync(shotsDir, { recursive: true });
	mkdirSync(scratchDir, { recursive: true });

	const session = {
		page,
		slug,
		docsDir,
		// For files a walkthrough makes on the spot, which never reach the site.
		scratchDir,
		marks,
		shots,

		/** The video starts here; everything before it is the app loading. */
		begin() {
			marks.push({ kind: "start", at: seconds() });
		},

		end() {
			marks.push({ kind: "end", at: seconds() });
		},

		/** One line under the page in the video; empty text hides it. */
		async caption(text) {
			await page.evaluate((line) => window.__guide.caption(line), text ?? "");
		},

		/** Moves the drawn pointer onto the element and lets it arrive. */
		async point(locator) {
			await locator.scrollIntoViewIfNeeded();
			const box = await locator.boundingBox();
			if (!box) throw new Error(`${slug}: nothing to point at`);
			await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
			await page.waitForTimeout(POINTER_TRAVEL_MS);
		},

		async click(locator, { caption, ...options } = {}) {
			if (caption !== undefined) await session.caption(caption);
			await session.point(locator);
			await locator.click(options);
			await page.waitForTimeout(350);
		},

		/** Types as a person would, so the video shows the words arrive. */
		async type(locator, text, { caption, delay = 32 } = {}) {
			await session.click(locator, { caption });
			await locator.pressSequentially(text, { delay });
			await page.waitForTimeout(300);
		},

		/**
		 * Waits for "is ready" notices to close, before clicking anything under
		 * them: a pointer resting on a notice keeps it open.
		 */
		async noticesGone(timeout = 20_000) {
			await page
				.locator("[data-sonner-toast]")
				.first()
				.waitFor({ state: "detached", timeout })
				.catch(() => {});
		},

		/** Leaves the screen still long enough to read. */
		async hold(ms = 1400) {
			await page.waitForTimeout(ms);
		},

		/** Time spent waiting on the app or a model, which the video plays faster. */
		async waitFor(work, { caption } = {}) {
			if (caption !== undefined) await session.caption(caption);
			const from = seconds();
			await work();
			marks.push({ kind: "wait", from, to: seconds() });
		},

		/**
		 * Saves a screenshot as `<nn>-<name>.webp` in the guide's folder: the window,
		 * or the box around `clip` (a locator, or several), or `region` in CSS pixels.
		 */
		async shot(name, { clip, region, pad = 12, quality, keepNotices = false } = {}) {
			const viewport = page.viewportSize();
			let box = region;
			if (clip) {
				const boxes = await Promise.all(
					(Array.isArray(clip) ? clip : [clip]).map((locator) => locator.boundingBox())
				);
				if (boxes.some((found) => !found))
					throw new Error(`${slug}: ${name} has nothing to clip to`);
				const left = Math.min(...boxes.map((found) => found.x));
				const top = Math.min(...boxes.map((found) => found.y));
				const right = Math.max(...boxes.map((found) => found.x + found.width));
				const bottom = Math.max(...boxes.map((found) => found.y + found.height));
				box = {
					x: left - pad,
					y: top - pad,
					width: right - left + pad * 2,
					height: bottom - top + pad * 2,
				};
			}
			if (box) {
				const x = Math.max(0, Math.floor(box.x));
				const y = Math.max(0, Math.floor(box.y));
				box = {
					x,
					y,
					width: Math.min(viewport.width - x, Math.ceil(box.width)),
					height: Math.min(viewport.height - y, Math.ceil(box.height)),
				};
			}
			const file = `${String(shots.length + 1).padStart(2, "0")}-${name}`;
			const png = join(scratchDir, `${file}.png`);
			const from = seconds();
			await page.evaluate((keep) => window.__guide.hide({ keepNotices: keep }), keepNotices);
			await page.screenshot({
				path: png,
				...(box && { clip: box }),
				animations: "disabled",
				caret: "hide",
			});
			await page.evaluate(() => window.__guide.show());
			marks.push({ kind: "shot", from, to: seconds() });
			const webp = join(shotsDir, `${file}.webp`);
			await pngToWebp(png, webp, quality);
			shots.push({ name, file: `${file}.webp`, path: webp });
			return webp;
		},

		/** The video's still before it plays: the window as the walkthrough leaves it, without the overlay. */
		async poster() {
			const png = join(scratchDir, "poster.png");
			await page.evaluate(() => window.__guide.hide());
			await page.screenshot({ path: png, animations: "disabled", caret: "hide" });
			await pngToWebp(png, join(shotsDir, "poster.webp"), 80);
		},
	};
	return session;
}
