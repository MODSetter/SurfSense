/**
 * /docs/v2/guides/analyse-a-spreadsheet: the agent answers a question about a
 * CSV's numbers, then charts them in a Word document. The chart goes in a
 * document because the chat shows an analysis's chart only as its file's name.
 */

import {
	askAgent,
	conversation,
	deleteSources,
	newAgentChat,
	uploadSource,
	useAgentModel,
} from "./agent-chat.mjs";
import { closeArtifact } from "./studio.mjs";

const DATA = "known-exploited-vulnerabilities.csv";

export const analyseASpreadsheet = {
	slug: "analyse-a-spreadsheet",
	async prepare({ apiUrl }) {
		await deleteSources(apiUrl, [DATA]);
	},
	async before(g) {
		await closeArtifact(g);
		await useAgentModel(g);
		await uploadSource(g, `Data/${DATA}`);
	},
	async run(g) {
		const { page } = g;
		await newAgentChat(g);
		await askAgent(
			g,
			"Which ten vendors have the most known exploited vulnerabilities in the CISA list?",
			{
				stepsShot: "working",
				caption: "Ask about the numbers in a spreadsheet or CSV",
			}
		);
		await g.caption("It runs a short analysis on a copy of the file, and answers from the result");
		await g.hold(2000);
		await g.shot("answer", { clip: conversation(page), pad: 0 });

		await askAgent(g, "Put that table and a bar chart of it in a one-page Word document", {
			caption: "Ask for a chart in a document",
		});
		await g.click(page.getByRole("button", { name: /^Created / }).last(), {
			caption: "Open the document",
		});
		const viewer = page.getByRole("complementary", { name: "Artifact" });
		await viewer.getByRole("document").waitFor();
		await g.noticesGone();
		await g.hold(2000);
		await g.shot("chart-document");
	},
};
