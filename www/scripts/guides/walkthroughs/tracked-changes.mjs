/** /docs/v2/guides/tracked-changes: the agent edits a Word source into a revised copy, every edit a tracked change. */

import {
	askAgent,
	conversation,
	deleteSources,
	newAgentChat,
	switchToAgentModel,
	uploadSource,
} from "./agent-chat.mjs";
import { closeArtifact } from "./studio.mjs";

const PLAN = "Written Information Security Plan.docx";

export const trackedChanges = {
	slug: "tracked-changes",
	async prepare({ apiUrl }) {
		await deleteSources(apiUrl, [PLAN]);
	},
	async before(g) {
		await closeArtifact(g);
		await switchToAgentModel(g);
		await uploadSource(g, `Firm policies/${PLAN}`);
	},
	async run(g) {
		const { page } = g;
		await newAgentChat(g);
		await askAgent(
			g,
			"In the Written Information Security Plan, require multi-factor authentication for all remote access, and change the annual review to every six months",
			{ caption: "Ask for the edits, naming your Word file" }
		);
		await g.caption("The agent edits a copy: your file stays as it was");
		await g.hold(1600);
		await g.shot("reply", { clip: conversation(page), pad: 0 });

		await g.click(page.getByRole("button", { name: /^Revised / }).last(), {
			caption: "Open the revised copy",
		});
		const viewer = page.getByRole("complementary", { name: "Artifact" });
		await viewer.getByRole("button", { name: "Accept all" }).waitFor();
		await g.noticesGone();
		await g.caption("Every edit is a tracked change, as in Word");
		await g.hold(2000);
		await g.shot("revised-copy", { quality: 78 });
		await g.point(viewer.getByRole("link", { name: "With changes" }));
		await g.caption("Download it With changes, or Clean");
		await g.hold(1600);
		await g.shot("downloads", {
			clip: [
				viewer.getByRole("link", { name: "With changes" }),
				viewer.getByRole("button", { name: "Reject all" }),
			],
			pad: 16,
		});
	},
};
