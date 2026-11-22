/** /docs/v2/guides/pick-sources: the ticks in Sources decide what chat, Studio and the agent use. */

import { FOLDER, sourcesPanel } from "./add-sources.mjs";

/** The header's toggle reads Select all until everything is ticked, then Clear. */
function toggle(page, name) {
	return sourcesPanel(page)
		.getByRole("region", { name: "Sources" })
		.getByRole("button", { name, exact: true });
}

export const pickSources = {
	slug: "pick-sources",
	async before(g) {
		const { page } = g;
		await sourcesPanel(page).getByRole("treeitem", { name: FOLDER }).waitFor();
		const expand = sourcesPanel(page).getByRole("button", { name: `Expand ${FOLDER}` });
		if (await expand.count()) await expand.click();
		await sourcesPanel(page).getByRole("treeitem", { name: "Security fundamentals.pdf" }).waitFor();
		if (await toggle(page, "Select all").count()) await toggle(page, "Select all").click();
	},
	async run(g) {
		const { page } = g;
		const sources = sourcesPanel(page).getByRole("region", { name: "Sources" });
		const count = page.getByRole("region", { name: "Conversation" }).getByText(/^\d+ sources?$/);

		const file = sources.getByRole("treeitem", { name: "Security fundamentals.pdf" });
		await g.click(file.getByRole("checkbox"), { caption: "Untick a source to leave it out" });
		await g.hold(1000);
		await g.shot("untick", {
			clip: [
				sources.getByRole("heading", { name: "Sources" }),
				sources.getByRole("treeitem").last(),
				count,
			],
		});

		await g.click(toggle(page, "Select all"), { caption: "Select all ticks every source" });
		await g.hold(700);
		await g.click(toggle(page, "Clear"), { caption: "Clear unticks them all" });
		await g.hold(900);
		await g.click(sources.getByRole("treeitem", { name: FOLDER }).getByRole("checkbox"), {
			caption: "Tick a folder to use everything in it, and files you add to it later",
		});
		await g.hold(1200);
		await g.shot("folder", {
			clip: [
				sources.getByRole("heading", { name: "Sources" }),
				sources.getByRole("treeitem").last(),
				count,
			],
		});
		await g.caption("The chat box shows how many sources are ticked");
		await g.hold(1600);
	},
};
