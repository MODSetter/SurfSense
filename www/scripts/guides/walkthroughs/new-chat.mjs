/** A new chat, in the mode a walkthrough needs: the mode is picked before the first message. */

export async function startChat(g, mode, { caption } = {}) {
	const { page } = g;
	const sidebar = page
		.getByRole("complementary")
		.filter({ has: page.getByRole("heading", { name: "SurfSense" }) });
	await g.click(sidebar.getByRole("button", { name: "New chat" }), {
		caption: caption ?? "Click New chat",
	});
	await page.getByRole("textbox", { name: "Message" }).waitFor();
	if (!mode) return;
	const picker = page.getByRole("button", { name: /^Chat mode/ });
	if (!(await picker.textContent())?.includes(mode)) {
		await g.click(picker, { caption: `Pick ${mode} under Mode for this chat` });
		await g.click(
			page.getByRole("menuitemradio", { name: new RegExp(`^${mode.replace(/[()]/g, "\\$&")}`) })
		);
	}
}

/** Sends `question` and waits out the reply, which the video plays faster. */
export async function ask(g, question, { caption = "Type your question and press Enter" } = {}) {
	const { page } = g;
	await g.type(page.getByRole("textbox", { name: "Message" }), question, { caption, delay: 22 });
	await page.keyboard.press("Enter");
	await g.waitFor(
		() =>
			page
				.getByRole("status")
				.filter({ hasText: "Reply finished" })
				.last()
				.waitFor({ state: "attached", timeout: 600_000 }),
		{ caption: "The model reads the passages that match, then answers (sped up)" }
	);
}
