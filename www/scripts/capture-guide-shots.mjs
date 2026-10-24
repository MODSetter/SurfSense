/**
 * Regenerates the desktop-app screenshots `/license/activate` carries.
 *
 * Run it against a desktop app already running in dev, from `www`:
 *
 *   node scripts/capture-guide-shots.mjs
 *   SIDECAR=http://127.0.0.1:52316 node scripts/capture-guide-shots.mjs
 *
 * The sidecar picks a fresh port every launch, so `SIDECAR` usually has to be
 * passed. Find it by probing the app's own health route across the listening
 * loopback ports, or read it out of the electron dev log.
 *
 * Why a browser and not the Electron window: the renderer reads exactly one
 * required field off the preload bridge (`apiUrl` in `lib/api.ts`) and every
 * other read is optional-chained, so pointing a page at the Vite server with
 * that field injected gives the real app against the real local backend. The
 * updates bridge is stubbed too, because `UpdateSettings` renders null without
 * it and Settings would come out a row short of the packaged app.
 *
 * License status is intercepted rather than read: it pins both the empty and
 * the active state for the shots, and keeps a real licensee address and expiry
 * out of a public page.
 */

import { chromium } from "@playwright/test";

const SIDECAR = process.env.SIDECAR ?? "http://127.0.0.1:52316";
const APP = process.env.APP ?? "http://127.0.0.1:5173/";

const NONE = { state: "none", plan: null, email: null, expiry: null, max_users: null };
// Per contract 01, `maxUsers` is null for anything but a team key.
const ACTIVE = {
	state: "active",
	plan: "individual",
	email: "you@example.com",
	expiry: "2027-09-17T12:00:00Z",
	max_users: null,
};

let status = NONE;

const browser = await chromium.launch();
const page = await browser.newPage({
	viewport: { width: 1280, height: 800 },
	deviceScaleFactor: 2,
});
await page.addInitScript((apiUrl) => {
	window.surfsense = {
		apiUrl,
		platform: "win32",
		updates: {
			prefs: async () => ({ automatic: false }),
			state: async () => ({ status: "idle" }),
			check: async () => {},
			install: async () => {},
			onState: () => () => {},
		},
	};
}, SIDECAR);
await page.route("**/license/status", (route) =>
	route.fulfill({ json: status, headers: { "access-control-allow-origin": "*" } })
);

async function load() {
	await page.goto(APP, { waitUntil: "networkidle" });
	await page.waitForTimeout(4000);
}

async function openSettings(section) {
	await page.getByRole("button", { name: "Open settings" }).click();
	if (section !== "General") {
		await page.getByRole("dialog").getByRole("button", { name: section, exact: true }).click();
	}
}

/** The dialog's own box, inset: its rounded corners pick up whatever is behind. */
async function shotTopDialog(path) {
	const box = await page.locator('[role="dialog"]').last().boundingBox();
	await page.screenshot({
		path,
		clip: { x: box.x + 4, y: box.y + 4, width: box.width - 8, height: box.height - 8 },
	});
}

// ---- /license/activate ------------------------------------------------------

await load();
await openSettings("License");
await page.getByRole("button", { name: "Add license" }).waitFor();
await page.waitForTimeout(600);
await page.getByRole("dialog").screenshot({ path: "public/license/03-license-section.png" });

await page.getByRole("button", { name: "Add license" }).click();
// Not the "Choose license file" button: the hidden file input carries the same
// aria-label, so that name matches two elements.
await page.getByLabel("Paste license file").waitFor();
await page.waitForTimeout(600);
await shotTopDialog("public/license/04-add-dialog.png");

status = ACTIVE;
await load();
await openSettings("License");
await page.getByText("Individual plan").waitFor();
await page.waitForTimeout(600);
await page.getByRole("dialog").screenshot({ path: "public/license/05-active.png" });

await browser.close();
console.log("captured");
