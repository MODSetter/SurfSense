/** /docs/v2/guides/ask-and-cite: a Basic (Q&A) question, its cited answer, and the passage behind a citation. */

import { ask, startChat } from "./new-chat.mjs";

export const askAndCite = {
	slug: "ask-and-cite",
	async run(g) {
		const { page } = g;
		await startChat(g, null);
		const composer = page.getByRole("textbox", { name: "Message" });
		await g.click(page.getByRole("button", { name: /^Chat mode/ }), {
			caption: "Pick a mode before the first message",
		});
		const modes = page.getByRole("menu", { name: /^Chat mode/ });
		await modes.waitFor();
		await g.hold(900);
		await g.shot("mode", { clip: [modes, composer], pad: 24 });
		await g.click(modes.getByRole("menuitemradio", { name: /^Basic \(Q&A\)/ }), {
			caption: "Basic (Q&A) answers from your sources",
		});
		await ask(g, "What does the Govern function cover, and where should a small business start?");

		const conversation = page.getByRole("region", { name: "Conversation" });
		await g.caption("Each point carries a citation");
		await g.hold(1800);
		await g.shot("answer", { clip: conversation, pad: 0 });
		const chip = conversation.getByRole("button", { name: /^View cited chunk/ }).first();
		await g.click(chip, { caption: "Click a citation to see the passage it rests on" });
		const citation = page.getByRole("complementary", { name: "Citation" });
		await citation.waitFor();
		await g.hold(1800);
		await g.shot("citation");
		await g.click(citation.getByRole("button", { name: "Close citation" }), { caption: "" });
	},
};
