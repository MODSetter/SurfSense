/**
 * Captures the guides at /docs/v2/guides: boots a throwaway SurfSense, runs each
 * walkthrough in a recorded browser, and writes its screenshots to
 * `public/guides/<slug>/` and its video to the capture folder, for upload.
 *
 * From `www`, after building the renderer (`surfsense_local/frontend`:
 * `pnpm translations`, then `vite build`):
 *
 *   node scripts/guides/capture.mjs --fresh            every walkthrough, from a new install
 *   node scripts/guides/capture.mjs add-sources ...    only these, on the install as it stands
 *
 * `OPENROUTER_API_KEY` must be set: the server walkthrough sends it to the local
 * API in place of the placeholder it types, so no key is ever on screen. A
 * worktree without staged runtimes or bundled models borrows another checkout's
 * with `GUIDES_RUNTIMES_DIR` and `GUIDES_MODELS_DIR`.
 */

import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

import { bootApp } from "./app/boot-app.mjs";
import { installBridge } from "./app/bridge.mjs";
import { createWalkthroughSession } from "./capture/walkthrough-session.mjs";
import { fetchDemoDocuments } from "./demo-documents/fetch-demo-documents.mjs";
import { editVideo } from "./media/edit-video.mjs";
import { installOverlay } from "./page/overlay.mjs";
import { WALKTHROUGHS } from "./walkthroughs/index.mjs";

const REPO = fileURLToPath(new URL("../../../", import.meta.url));
const WWW = join(REPO, "www");
const CAPTURE = process.env.GUIDES_CAPTURE_DIR || join(REPO, ".capture");
const DATA = join(CAPTURE, "data", "guides");
const BRIDGE_STATE = join(CAPTURE, "data", "guides-bridge.json");
const VIEWPORT = { width: 1280, height: 800 };

function readBridgeState() {
	return existsSync(BRIDGE_STATE)
		? JSON.parse(readFileSync(BRIDGE_STATE, "utf8"))
		: { firstRunAsked: false };
}

const args = process.argv.slice(2);
const fresh = args.includes("--fresh");
const wanted = args.filter((arg) => !arg.startsWith("--"));
const unknown = wanted.filter(
	(slug) => !WALKTHROUGHS.some((walkthrough) => walkthrough.slug === slug)
);
if (unknown.length) throw new Error(`No walkthrough named ${unknown.join(", ")}`);
const chosen = wanted.length
	? WALKTHROUGHS.filter((walkthrough) => wanted.includes(walkthrough.slug))
	: WALKTHROUGHS;

mkdirSync(CAPTURE, { recursive: true });
// The folder ignores itself, so a capture in a checkout never shows up in git.
writeFileSync(join(CAPTURE, ".gitignore"), "*\n");
if (fresh) {
	rmSync(DATA, { recursive: true, force: true });
	rmSync(BRIDGE_STATE, { force: true });
}
const docsDir = await fetchDemoDocuments(join(CAPTURE, "docs"));
const version = readFileSync(join(REPO, "surfsense_local", "VERSION"), "utf8").trim();

const app = await bootApp({ dataDir: DATA });
// Chromium's own microphone, fed a spoken question, for the dictation walkthrough.
const browser = await chromium.launch({
	args: [
		"--use-fake-ui-for-media-stream",
		"--use-fake-device-for-media-stream",
		`--use-file-for-fake-audio-capture=${join(docsDir, "Voice", "Spoken question.wav")}`,
	],
});
try {
	for (const walkthrough of chosen) {
		const rawDir = join(CAPTURE, "raw", walkthrough.slug);
		const shotsDir = join(WWW, "public", "guides", walkthrough.slug);
		rmSync(rawDir, { recursive: true, force: true });
		rmSync(shotsDir, { recursive: true, force: true });
		// Undoes what an earlier take of this walkthrough left, so a retake starts as the first take did.
		await walkthrough.prepare?.({ apiUrl: app.apiUrl });

		const context = await browser.newContext({
			viewport: VIEWPORT,
			deviceScaleFactor: 2,
			locale: "en-US",
			colorScheme: "light",
			recordVideo: { dir: rawDir, size: VIEWPORT },
		});
		await context.addInitScript(installBridge, {
			apiUrl: app.apiUrl,
			version,
			...readBridgeState(),
		});
		await context.addInitScript(installOverlay);
		const page = await context.newPage();
		const startedAt = Date.now();
		await page.goto(app.appUrl);
		await page.locator("main").first().waitFor();
		await page.waitForTimeout(2500);

		const session = createWalkthroughSession({
			page,
			slug: walkthrough.slug,
			shotsDir,
			scratchDir: join(CAPTURE, "shots", walkthrough.slug),
			docsDir,
			startedAt,
		});
		console.log(`[guides] ${walkthrough.slug}`);
		// Puts the page as the walkthrough expects it; the video starts after.
		await walkthrough.before?.(session);
		session.begin();
		try {
			await walkthrough.run(session);
		} catch (error) {
			// What the page looked like when the walkthrough gave up, to fix the script against.
			const failures = join(CAPTURE, "failures");
			mkdirSync(failures, { recursive: true });
			await page.screenshot({ path: join(failures, `${walkthrough.slug}.png`) }).catch(() => {});
			const tree = await page
				.locator("body")
				.ariaSnapshot()
				.catch(() => "");
			writeFileSync(join(failures, `${walkthrough.slug}.aria.yml`), tree);
			throw error;
		}
		await session.caption("");
		await session.hold(1200);
		session.end();
		// After the end mark, so the hidden overlay never reaches the video.
		await session.poster();
		// Undoes what only this walkthrough needed, such as another chat model; the video has ended.
		await walkthrough.after?.(session);

		// The privacy answers live in Electron, which the stub stands in for: carry them to the next walkthrough.
		const privacy = await page.evaluate(() => window.surfsense.privacy.getState());
		writeFileSync(
			BRIDGE_STATE,
			JSON.stringify({
				firstRunAsked: privacy.firstRunAsked,
				updatesAutomatic: privacy.updates.automatic,
				usageStatistics: privacy.usageStatistics.enabled,
			})
		);
		const video = page.video();
		await context.close();
		mkdirSync(join(CAPTURE, "videos"), { recursive: true });
		const mp4 = join(CAPTURE, "videos", `${walkthrough.slug}.mp4`);
		const seconds = await editVideo({ raw: await video.path(), marks: session.marks, mp4 });
		// The guide page says how long its video runs; the upload reads it from here.
		writeFileSync(join(CAPTURE, "videos", `${walkthrough.slug}.json`), JSON.stringify({ seconds }));
		console.log(
			`[guides] ${walkthrough.slug}: ${session.shots.length} shots, ${seconds.toFixed(0)} s of video`
		);
	}
} finally {
	await browser.close();
	await app.stop();
}
