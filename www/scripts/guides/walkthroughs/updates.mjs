/**
 * /docs/v2/guides/updates: check for a newer version from the title bar, then
 * in Settings › About. The capture's Electron is a stub whose check answers as
 * the newest version does, so the guide shows a check that finds nothing new.
 * Update checks are on, as the set-up guide answered Yes to them.
 */

import { closeSettings, openSettingsSection } from "./open-settings.mjs";
import { closeArtifact } from "./studio.mjs";

const UP_TO_DATE = "SurfSense is up to date";

export const updates = {
	slug: "updates",
	async before(g) {
		await closeArtifact(g);
	},
	async run(g) {
		const { page } = g;
		await g.click(page.getByRole("button", { name: "Check for updates" }), {
			caption: "Click Check for updates, at the top right",
		});
		await page.locator("[data-sonner-toast]").filter({ hasText: UP_TO_DATE }).waitFor();
		await g.caption("SurfSense says whether a newer version is out");
		await g.hold(1600);
		await g.shot("check", {
			region: { x: 820, y: 0, width: 460, height: 110 },
			keepNotices: true,
		});

		const settings = await openSettingsSection(g, "About", {
			caption: "Settings › About shows the version you have",
		});
		await settings.getByRole("heading", { name: "About", exact: true }).waitFor();
		await g.noticesGone();
		await g.hold(1400);
		await g.shot("about", { clip: settings });
		await g.click(settings.getByRole("button", { name: "Check now" }), {
			caption: "Check now checks again",
		});
		await settings.getByText(UP_TO_DATE).waitFor();
		await g.hold(1200);
		await g.point(settings.getByRole("link", { name: "Release notes" }));
		await g.caption("Release notes says what each version changed");
		await g.hold(2000);
		await closeSettings(g);
	},
};
