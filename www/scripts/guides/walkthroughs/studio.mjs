/** Studio's formats, its Artifacts list and its viewer, as the Studio walkthroughs drive them. */

export function artifacts(page) {
	return page.getByRole("region", { name: "Artifacts" });
}

/** Opens a format's box, writes the prompt if there is one, and clicks Generate. */
export async function generate(g, format, { prompt, caption } = {}) {
	const { page } = g;
	await g.click(
		page
			.getByRole("region", { name: "Studio formats" })
			.getByRole("button", { name: format, exact: true }),
		{
			caption: caption ?? `Click ${format}`,
		}
	);
	const box = page.getByRole("dialog", { name: format });
	await box.waitFor();
	if (prompt)
		await g.type(box.getByRole("textbox"), prompt, {
			caption: "Write a prompt to steer it, if you want",
			delay: 18,
		});
	return box;
}

/** Resolves once nothing in the Artifacts list is still being made. */
export async function artifactsReady(page, timeout = 900_000) {
	await artifacts(page)
		.getByRole("status", { name: /^Processing/ })
		.first()
		.waitFor({ state: "detached", timeout });
}

/** The artifact `index` rows down, newest first, by its title button. */
export function artifactRow(page, index) {
	return artifacts(page).getByRole("listitem").nth(index).getByRole("button").first();
}

/**
 * Deletes the artifacts in My Workspace, so a take starts as the first take did.
 * `keep` spares the oldest few: an earlier walkthrough's, which a later one uses.
 */
export async function clearArtifacts(apiUrl, { keep = 0 } = {}) {
	const workspaces = await (await fetch(`${apiUrl}/workspaces`)).json();
	const mine = workspaces.find((workspace) => workspace.name === "My Workspace");
	const all = await (await fetch(`${apiUrl}/workspaces/${mine.id}/artifacts`)).json();
	const oldestFirst = [...all].sort((a, b) => a.id - b.id);
	for (const artifact of oldestFirst.slice(keep)) {
		await fetch(`${apiUrl}/artifacts/${artifact.id}/cancel`, { method: "POST" }).catch(() => {});
		await fetch(`${apiUrl}/artifacts/${artifact.id}`, { method: "DELETE" });
	}
}

/** Deletes My Workspace's artifacts whose title starts with `prefix`, such as an earlier take's copies. */
export async function deleteArtifactsTitled(apiUrl, prefix) {
	const workspaces = await (await fetch(`${apiUrl}/workspaces`)).json();
	const mine = workspaces.find((workspace) => workspace.name === "My Workspace");
	const all = await (await fetch(`${apiUrl}/workspaces/${mine.id}/artifacts`)).json();
	for (const artifact of all.filter((each) => each.title?.startsWith(prefix))) {
		await fetch(`${apiUrl}/artifacts/${artifact.id}`, { method: "DELETE" });
	}
}

export async function closeArtifact(g) {
	const close = g.page.getByRole("button", { name: "Close artifact" });
	if (!(await close.count())) return;
	// The close button sits where "is ready" notices appear.
	await g.noticesGone();
	await g.click(close, { caption: "" });
}
