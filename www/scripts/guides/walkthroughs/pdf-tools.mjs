/** /docs/v2/guides/pdf-tools: the agent merges two PDF sources and numbers the pages of the result. */

import { askAgent, conversation, newAgentChat, useAgentModel } from "./agent-chat.mjs";
import { artifactRow, closeArtifact } from "./studio.mjs";

export const pdfTools = {
	slug: "pdf-tools",
	async before(g) {
		await closeArtifact(g);
		await useAgentModel(g);
	},
	async run(g) {
		const { page } = g;
		await newAgentChat(g);
		await askAgent(
			g,
			"Merge CSF quick start.pdf and Security fundamentals.pdf into one PDF, then add page numbers",
			{
				caption: "Ask for what to do with your PDFs",
			}
		);
		await g.caption("Each tool is a step, and each result is a new PDF in Studio");
		await g.hold(1600);
		await g.shot("steps", { clip: conversation(page), pad: 0 });
		// A PDF tool's step names what it did but doesn't link the file: the newest artifact is it.
		await g.noticesGone();
		await g.click(artifactRow(page, 0), { caption: "Open it from Studio" });
		const viewer = page.getByRole("complementary", { name: "Artifact" });
		await viewer.waitFor();
		await page.waitForTimeout(2500);
		await g.hold(1500);
		await g.shot("merged-pdf", { quality: 78 });
	},
};
