/**
 * /docs/v2/guides/voice-input: dictate a question in the chat box. The
 * microphone is Chromium's fake one, which the runner feeds a spoken question
 * (demo-documents: "Voice/Spoken question.wav"); needs a speech model, which
 * transcribe-a-recording downloads.
 */

import { startChat } from "./new-chat.mjs";
import { closeArtifact } from "./studio.mjs";

export const voiceInput = {
	slug: "voice-input",
	async before(g) {
		await closeArtifact(g);
	},
	async run(g) {
		const { page } = g;
		await startChat(g, "Basic (Q&A)");
		const composer = page.getByRole("textbox", { name: "Message" });
		const mic = page.getByRole("button", { name: /voice input/i }).first();
		await g.click(mic, { caption: "Click the microphone beside Send" });
		await g.caption("Speak: your words arrive a phrase at a time");
		await page.waitForFunction(
			() =>
				(document.querySelector('[aria-label="Message"]')?.textContent ?? "").trim().length > 20,
			undefined,
			{ timeout: 60_000, polling: 500 }
		);
		await g.hold(1500);
		await g.shot("dictating", { clip: page.getByRole("region", { name: "Conversation" }), pad: 0 });
		const insert = page.getByRole("button", { name: /Stop and insert/i });
		await g.click(insert, { caption: "Click ✓ or press Enter to keep the text" });
		await g.hold(1500);
		await g.shot("inserted", { clip: page.getByRole("region", { name: "Conversation" }), pad: 0 });
		await g.caption("Nothing is sent until you send it");
		await g.hold(1500);
	},
};
