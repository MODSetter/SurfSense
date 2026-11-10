/** /docs/v2/guides/workspaces: create a workspace, switch, rename it, then delete it, leaving the first one as it was. */

const NAME = "Course notes";
const RENAMED = "Biology notes";

export const workspaces = {
	slug: "workspaces",
	/** A retake starts with My Workspace alone, as the first take did. */
	async prepare({ apiUrl }) {
		const all = await (await fetch(`${apiUrl}/workspaces`)).json();
		for (const workspace of all.filter((each) => each.name !== "My Workspace")) {
			await fetch(`${apiUrl}/workspaces/${workspace.id}`, { method: "DELETE" });
		}
	},
	async run(g) {
		const { page } = g;
		const rail = page.getByRole("navigation", { name: "Workspaces" });
		await g.click(rail.getByRole("button", { name: "Create workspace" }), {
			caption: "Click + in the workspace rail",
		});
		const create = page.getByRole("dialog", { name: "Create workspace" });
		await create.waitFor();
		await g.type(create.getByRole("textbox", { name: "Workspace name" }), NAME, {
			caption: "Name it",
		});
		await g.shot("create", { clip: create });
		await g.click(create.getByRole("button", { name: "Create" }), { caption: "Click Create" });
		await rail.getByRole("button", { name: NAME }).waitFor();
		await g.caption("The new workspace opens, empty");
		await g.hold(1700);
		await g.shot("new-workspace");

		await g.click(rail.getByRole("button", { name: "My Workspace" }), {
			caption: "Click a workspace to switch to it",
		});
		await g.hold(1600);

		// Measured before the menu opens: an open menu hides the rest of the page from role queries.
		const railBox = await rail.boundingBox();
		await g.click(rail.getByRole("button", { name: NAME }), {
			button: "right",
			caption: "Right-click a workspace to rename or delete it",
		});
		const menu = page.getByRole("menu");
		await menu.waitFor();
		await g.hold(900);
		const menuBox = await menu.boundingBox();
		const right = Math.max(railBox.x + railBox.width, menuBox.x + menuBox.width) + 12;
		const bottom = Math.max(menuBox.y + menuBox.height, railBox.y + 160) + 12;
		await g.shot("workspace-menu", {
			region: { x: 0, y: railBox.y, width: right, height: bottom - railBox.y },
		});
		await g.click(menu.getByRole("menuitem", { name: "Rename" }));
		const rename = page.getByRole("dialog", { name: "Rename workspace" });
		const field = rename.getByRole("textbox", { name: "Workspace name" });
		await field.waitFor();
		await field.fill("");
		await g.type(field, RENAMED, { caption: "Type the new name, then click Rename" });
		await g.shot("rename", { clip: rename });
		await g.click(rename.getByRole("button", { name: "Rename" }));
		await rail.getByRole("button", { name: RENAMED }).waitFor();
		await g.hold(900);

		await g.click(rail.getByRole("button", { name: RENAMED }), {
			button: "right",
			caption: "To delete one, right-click it and choose Delete",
		});
		await g.click(page.getByRole("menu").getByRole("menuitem", { name: "Delete" }));
		const confirm = page.getByRole("alertdialog");
		await confirm.waitFor();
		await g.caption("Deleting a workspace deletes its chats and sources for good");
		await g.hold(1600);
		await g.shot("delete", { clip: confirm });
		await g.click(confirm.getByRole("button", { name: "Delete workspace" }));
		await rail.getByRole("button", { name: RENAMED }).waitFor({ state: "detached" });
		await g.hold(1000);
	},
};
