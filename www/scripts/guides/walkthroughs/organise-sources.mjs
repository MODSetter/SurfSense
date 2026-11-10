/** /docs/v2/guides/organise-sources: a note, a folder to move it into, a rename, and a PDF preview. */

import { sourcesPanel } from "./add-sources.mjs";
import { closeArtifact } from "./studio.mjs";

const NOTE_TITLE = "Meeting notes";
const NOTE_TEXT =
	"Agreed today: turn on multi-factor sign-in for every account by Friday, and back up the shared drive each night.";
const FOLDER = "Notes";

/** Deletes an earlier take's folder, with the note filed in it, so a retake starts as the first did. */
async function removeEarlierTake(apiUrl) {
	const workspaces = await (await fetch(`${apiUrl}/workspaces`)).json();
	const mine = workspaces.find((workspace) => workspace.name === "My Workspace");
	const folders = await (await fetch(`${apiUrl}/workspaces/${mine.id}/folders`)).json();
	for (const folder of folders.filter((each) => each.name === FOLDER)) {
		await fetch(`${apiUrl}/workspaces/${mine.id}/folders/${folder.id}`, { method: "DELETE" });
	}
	const documents = await (
		await fetch(`${apiUrl}/workspaces/${mine.id}/documents?document_type=NOTE&limit=100`)
	).json();
	for (const note of documents.filter((each) => each.title === NOTE_TITLE)) {
		await fetch(`${apiUrl}/workspaces/${mine.id}/documents/${note.id}`, { method: "DELETE" });
	}
}

export const organiseSources = {
	slug: "organise-sources",
	async prepare({ apiUrl }) {
		await removeEarlierTake(apiUrl);
	},
	async before(g) {
		await closeArtifact(g);
	},
	async run(g) {
		const { page } = g;
		const panel = sourcesPanel(page);
		const tree = panel.getByRole("tree", { name: "Sources" });

		await g.click(panel.getByRole("button", { name: "Add sources" }), {
			caption: "Click + in Sources",
		});
		await g.click(page.getByRole("menuitem", { name: "New note" }), { caption: "Choose New note" });
		const note = page.getByRole("dialog", { name: "New note" });
		await g.type(note.getByRole("textbox", { name: "Title" }), NOTE_TITLE, {
			caption: "Give it a title",
		});
		await g.type(note.getByRole("textbox", { name: "Note" }), NOTE_TEXT, {
			caption: "Write the note",
			delay: 10,
		});
		await g.shot("new-note", { clip: note });
		await g.click(note.getByRole("button", { name: "Save note" }), { caption: "Click Save note" });
		await tree.getByRole("treeitem", { name: NOTE_TITLE, exact: true }).waitFor();

		await g.click(panel.getByRole("button", { name: "Add sources" }), {
			caption: "Make a folder: + › New folder",
		});
		await g.click(page.getByRole("menuitem", { name: "New folder" }));
		const newFolder = page.getByRole("dialog", { name: "New folder" });
		await g.type(newFolder.getByRole("textbox", { name: "Name" }), FOLDER, {
			caption: "Name the folder",
		});
		await g.click(newFolder.getByRole("button", { name: "Create" }));
		await tree.getByRole("treeitem", { name: FOLDER, exact: true }).waitFor();

		await g.click(tree.getByRole("button", { name: `Actions for ${NOTE_TITLE}` }), {
			caption: "Each source’s ⋯ menu moves, renames or deletes it",
		});
		const menu = page.getByRole("menu");
		await menu.waitFor();
		await g.hold(900);
		await g.shot("source-menu", {
			clip: [panel.getByRole("heading", { name: "Sources" }), menu],
			pad: 16,
		});
		await g.click(menu.getByRole("menuitem", { name: "Move to…" }), {
			caption: "Choose Move to…, then the folder",
		});
		const move = page.getByRole("dialog", { name: `Move ${NOTE_TITLE}` });
		await move.waitFor();
		// The radio input itself is hidden; its label is what a person clicks.
		await g.click(move.getByText(FOLDER, { exact: true }));
		await g.hold(700);
		await g.shot("move-to", { clip: move });
		await g.click(move.getByRole("button", { name: "Move", exact: true }));
		await move.waitFor({ state: "detached" });
		await g.hold(1200);

		await g.click(
			panel
				.getByRole("button", { name: "Expand Security guides" })
				.or(panel.getByRole("button", { name: "Collapse Security guides" })),
			{
				caption: "",
			}
		);
		await g.click(tree.getByRole("button", { name: "Actions for NIST CSF 2.0.pdf" }), {
			caption: "Preview a PDF from its ⋯ menu",
		});
		await g.click(page.getByRole("menuitem", { name: "Preview" }));
		await page.waitForTimeout(3500);
		await g.caption("The PDF opens inside SurfSense");
		await g.hold(1500);
		await g.shot("preview");
	},
};
