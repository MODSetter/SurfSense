/** Settings opens from the gear at the bottom of the workspace rail; a section is a button in its sidebar. */

export async function openSettingsSection(g, section, { caption } = {}) {
	const { page } = g;
	await g.click(page.getByRole("button", { name: "Open settings" }), {
		caption: caption ?? "Open Settings",
	});
	const settings = page.getByRole("dialog", { name: "Settings" });
	await settings.waitFor();
	if (section !== "General") {
		await g.click(settings.getByRole("button", { name: section, exact: true }));
	}
	await g.hold(600);
	return settings;
}

export async function closeSettings(g) {
	const { page } = g;
	const settings = page.getByRole("dialog", { name: "Settings" });
	if (await settings.count()) {
		await g.click(settings.getByRole("button", { name: "Close" }).last());
		await settings.waitFor({ state: "detached" });
	}
}
