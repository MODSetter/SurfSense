/**
 * /docs/v2/guides/add-from-the-web: paste links to a page and a YouTube video,
 * allow the sites, and get both as sources. Both are NIST's, so public domain.
 */

import { sourcesPanel } from "./add-sources.mjs";

const PAGE = {
	url: "https://www.nist.gov/itl/smallbusinesscyber",
	title: "Small Business Cybersecurity Corner",
};
const VIDEO = {
	url: "https://www.youtube.com/watch?v=pPPiaGU12Og",
	title: "The NIST Cybersecurity Framework (CSF) 2.0",
};

/** A web source is ready once its row has a tick box. */
function readySource(page, title) {
	return sourcesPanel(page).getByRole("treeitem", { name: title }).getByRole("checkbox");
}

export const addFromTheWeb = {
	slug: "add-from-the-web",
	async run(g) {
		const { page } = g;
		const panel = sourcesPanel(page);
		await g.click(panel.getByRole("button", { name: "Add sources" }), {
			caption: "Click + in the Sources panel",
		});
		await g.click(page.getByRole("menuitem", { name: "Add from the web…" }), {
			caption: "Choose Add from the web…",
		});
		const dialog = page.getByRole("dialog", { name: "Add from the web" });
		await dialog.waitFor();
		await g.hold(1000);
		await g.shot("web-dialog", { clip: dialog });

		const box = dialog.getByRole("textbox", { name: "Search or paste links" });
		await g.click(box, { caption: "Paste links to pages and videos" });
		// A paste, as a reader would do it, rather than typing the addresses out.
		await box.fill(`${PAGE.url} ${VIDEO.url}`);
		await g.hold(700);
		await page.keyboard.press("Enter");
		const addAll = dialog.getByRole("button", { name: /^Add all/ });
		await addAll.waitFor();
		await g.hold(1100);
		await g.shot("links", { clip: dialog });
		await g.click(addAll, { caption: "Click Add on one, or Add all" });

		const ask = page.getByRole("alertdialog");
		await ask.waitFor();
		await g.caption("SurfSense asks before it reaches a site");
		await g.hold(1500);
		await g.shot("allow-site", { clip: ask });
		await g.click(ask.getByRole("button", { name: "Allow" }));
		await dialog.getByText("Added").first().waitFor();
		await g.hold(1000);
		await g.click(dialog.getByRole("button", { name: "Close" }).first(), { caption: "" });

		await g.waitFor(
			async () => {
				await readySource(page, PAGE.title).waitFor({ timeout: 300_000 });
				await readySource(page, VIDEO.title).waitFor({ timeout: 300_000 });
			},
			{ caption: "SurfSense reads the page, and the video’s transcript (sped up)" }
		);
		await g.caption("The page and the video are sources now");
		await g.hold(1700);
		await g.shot("web-sources", {
			clip: [panel.getByRole("heading", { name: "Sources" }), panel.getByRole("treeitem").last()],
			pad: 16,
		});
	},
};
