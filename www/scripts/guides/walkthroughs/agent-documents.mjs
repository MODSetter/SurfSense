/** /docs/v2/guides/agent-documents: an Agentic chat writes a Word report from the sources, then changes it on request. */

import { askAgent, conversation, newAgentChat, useAgentModel } from "./agent-chat.mjs";
import { closeArtifact } from "./studio.mjs";

export const agentDocuments = {
	slug: "agent-documents",
	async before(g) {
		await closeArtifact(g);
		await useAgentModel(g);
	},
	async run(g) {
		const { page } = g;
		await newAgentChat(g);
		await askAgent(
			g,
			"Write a two-page Word report for a small business owner on getting started with the Cybersecurity Framework",
			{
				stepsShot: "working",
				caption: "Ask for the document you want",
			}
		);
		await g.caption("Each step is one line; the file it made is linked");
		await g.hold(1800);
		await g.shot("reply", { clip: conversation(page), pad: 0 });

		await g.click(page.getByRole("button", { name: /^Created / }).last(), {
			caption: "Click the file to open it in Studio",
		});
		const viewer = page.getByRole("complementary", { name: "Artifact" });
		await viewer.getByRole("document").waitFor();
		await g.noticesGone();
		await g.hold(1800);
		await g.shot("document", { quality: 78 });

		await askAgent(g, "Add a short section on backing up your data", {
			caption: "Ask for a change in the same chat",
		});
		await viewer
			.getByRole("button", { name: /^Showing v2/ })
			.waitFor({ timeout: 120_000 })
			.catch(() => {});
		await g.noticesGone();
		await g.caption("The change is the document’s next version");
		await g.hold(1800);
		await g.shot("version-2", { quality: 78 });
	},
};
