/** /docs/v2/guides/add-sources: upload a folder of documents and watch them become ready. */

import { join } from "node:path";

export const FOLDER = "Security guides";

export function sourcesPanel(page) {
	return page.getByRole("complementary", { name: "Workspace sources" });
}

/** Resolves once no source in the panel is still being read. */
export async function sourcesReady(page, timeout = 900_000) {
	await page.waitForFunction(
		() => !document.querySelector('[role="tree"] [role="status"][aria-label^="Processing"]'),
		undefined,
		{ timeout, polling: 1000 }
	);
}

export const addSources = {
	slug: "add-sources",
	async run(g) {
		const { page } = g;
		const panel = sourcesPanel(page);
		await g.click(panel.getByRole("button", { name: "Add sources" }), {
			caption: "Click + in the Sources panel",
		});
		const menu = page.getByRole("menu", { name: "Add sources" });
		await menu.waitFor();
		await g.hold(900);
		await g.shot("add-menu", {
			clip: [panel.getByRole("heading", { name: "Sources" }), menu],
			pad: 20,
		});

		const chooser = page.waitForEvent("filechooser");
		await g.click(menu.getByRole("menuitem", { name: "Upload folder…" }), {
			caption: "Choose Upload folder…, then pick the folder",
		});
		await (await chooser).setFiles(join(g.docsDir, FOLDER));
		const folder = panel.getByRole("treeitem", { name: FOLDER });
		await folder.waitFor();
		await g.click(panel.getByRole("button", { name: `Expand ${FOLDER}` }), {
			caption: "Each file is read on this computer",
		});
		await g.hold(800);
		await g.shot("reading", {
			clip: [panel.getByRole("heading", { name: "Sources" }), panel.getByRole("treeitem").last()],
			pad: 16,
		});
		await g.waitFor(() => sourcesReady(page), {
			caption: "A source is ready once it’s searchable (sped up)",
		});
		await g.caption("Ready sources are ticked, so chat and Studio can use them");
		await g.hold(1800);
		await g.shot("ready");
	},
};
