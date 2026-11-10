/**
 * /docs/v2/guides/privacy-network: Settings › Network lists every place
 * SurfSense can send data. Untick one to block it, and SurfSense asks again the
 * next time you do something that needs it. The site is the one the web
 * research guide allowed; nothing is fetched, since the question is cancelled.
 */

import { sourcesPanel } from "./add-sources.mjs";
import { setHostAllowed } from "./egress.mjs";
import { closeSettings, openSettingsSection } from "./open-settings.mjs";
import { closeArtifact } from "./studio.mjs";

const SITE = "www.cisa.gov";
const PAGE = "https://www.cisa.gov/resources-tools/resources/cyber-essentials";

export const privacyNetwork = {
	slug: "privacy-network",
	/** The take unticks the site, so it starts allowed, as the web research guide left it. */
	async prepare({ apiUrl }) {
		await setHostAllowed(apiUrl, SITE, true);
	},
	async before(g) {
		await closeArtifact(g);
	},
	async run(g) {
		const { page } = g;
		const settings = await openSettingsSection(g, "Network", {
			caption: "Open Settings, then Network",
		});
		await settings.getByRole("heading", { name: "Network", exact: true }).waitFor();
		await g.caption("Every place SurfSense can send data, and its last call");
		await g.hold(2200);
		await g.shot("network", { clip: settings });

		const allow = settings.getByRole("checkbox", { name: `Allow ${SITE}` });
		await g.click(allow, { caption: "Untick one to block it outright" });
		while ((await allow.getAttribute("aria-checked")) !== "false") {
			await page.waitForTimeout(200);
		}
		await g.hold(1400);
		const row = settings
			.getByRole("listitem")
			.filter({ has: page.getByRole("checkbox", { name: `Allow ${SITE}` }) });
		await g.shot("blocked", { clip: row, pad: 16 });
		await closeSettings(g);

		const panel = sourcesPanel(page);
		await g.click(panel.getByRole("button", { name: "Add sources" }), {
			caption: "The next time you do something that needs it…",
		});
		await g.click(page.getByRole("menuitem", { name: "Add from the web…" }));
		const dialog = page.getByRole("dialog", { name: "Add from the web" });
		await dialog.waitFor();
		const links = dialog.getByRole("textbox", { name: "Search or paste links" });
		await g.click(links);
		await links.fill(PAGE);
		await g.hold(600);
		await page.keyboard.press("Enter");
		const add = dialog.getByRole("button", { name: /^Add/ }).first();
		await add.waitFor();
		await g.hold(800);
		await g.click(add);

		const ask = page.getByRole("alertdialog", { name: `Allow reading pages from ${SITE}?` });
		await ask.waitFor();
		await g.caption("…SurfSense asks first, and says what the site gets");
		await g.hold(2400);
		await g.shot("ask", { clip: ask });
		await g.click(ask.getByRole("button", { name: "Cancel" }), {
			caption: "Cancel leaves it off; Allow turns it back on",
		});
		await g.hold(1600);
		await g.click(dialog.getByRole("button", { name: "Close" }).first(), { caption: "" });
	},
};
