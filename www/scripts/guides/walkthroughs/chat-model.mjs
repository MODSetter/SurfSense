/**
 * Switches the chat model to one of the OpenRouter server's, through Settings,
 * outside any recording: a walkthrough whose task the usual model can't do well
 * uses another, then puts the usual one back.
 */

export const USUAL_MODEL = "qwen/qwen3.8-27b";

export async function switchChatModel(g, model) {
	const { page } = g;
	await page.getByRole("button", { name: "Open settings" }).click();
	const settings = page.getByRole("dialog", { name: "Settings" });
	await settings.getByRole("button", { name: "Text gen", exact: true }).click();
	const inUse = settings.getByRole("region", { name: "chat model in use" });
	await inUse.waitFor();
	if (!(await inUse.innerText()).includes(model)) {
		const show = settings.getByRole("button", { name: /^Show chat models/ });
		if (await show.count()) await show.click();
		await settings.getByPlaceholder("Search chat models").fill(model);
		await settings.getByRole("button", { name: `Use ${model}`, exact: true }).click();
		const confirm = page.getByRole("dialog", { name: `Use ${model} for chat?` });
		await confirm.getByRole("button", { name: "Use without testing" }).click();
		await confirm.waitFor({ state: "detached" });
	}
	await settings.getByRole("button", { name: "Close" }).last().click();
	await settings.waitFor({ state: "detached" });
}
