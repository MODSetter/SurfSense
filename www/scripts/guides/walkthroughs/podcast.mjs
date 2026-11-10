/**
 * /docs/v2/guides/podcast: a short episode from the ticked sources, voiced on
 * this computer. Drafted with Claude Haiku 5.5: Qwen3.8 27B returned empty
 * podcast scripts on OpenRouter (10 Nov 2026), so this walkthrough borrows a
 * model that drafts them, then gives the usual one back.
 */

import { switchChatModel, USUAL_MODEL } from "./chat-model.mjs";
import { artifactRow, artifacts, artifactsReady, closeArtifact } from "./studio.mjs";

const DRAFTING_MODEL = "anthropic/claude-haiku-5.5";

export const podcast = {
	slug: "podcast",
	async before(g) {
		await closeArtifact(g);
		await switchChatModel(g, DRAFTING_MODEL);
	},
	async run(g) {
		const { page } = g;
		await g.click(
			page
				.getByRole("region", { name: "Studio formats" })
				.getByRole("button", { name: "Podcast", exact: true }),
			{
				caption: "In Studio, click Podcast",
			}
		);
		const brief = page.getByRole("dialog", { name: "Podcast" });
		await g.waitFor(
			() => brief.getByRole("combobox", { name: "Style" }).waitFor({ timeout: 120_000 }),
			{
				caption: "SurfSense prepares a brief from your sources",
			}
		);
		// A native select: its open list never reaches a screenshot, so the pointer only shows where it is.
		await g.point(brief.getByRole("combobox", { name: "Style" }));
		await g.caption("Pick a style, such as Conversational or Interview");
		await g.hold(1400);
		await g.click(brief.getByRole("button", { name: "Short ~3 min" }), {
			caption: "Pick a length",
		});
		await g.point(brief.getByRole("group", { name: "Speaker 1" }));
		await g.caption("Each speaker has a role and a voice");
		await g.hold(1600);
		await g.shot("brief", { clip: brief });
		await g.click(brief.getByRole("button", { name: "Generate" }), { caption: "Click Generate" });
		await g.hold(1200);
		await g.shot("generating", { clip: artifacts(page) });
		await g.waitFor(() => artifactsReady(page), {
			caption: "It writes the script, then voices it on this computer (sped up)",
		});
		await g.noticesGone();
		await g.click(artifactRow(page, 0), { caption: "Open it to listen and read along" });
		const viewer = page.getByRole("complementary", { name: "Artifact" });
		await viewer.getByText("Transcript").waitFor();
		await g.hold(1800);
		await g.shot("player", { clip: viewer, pad: 0 });
		await g.point(viewer.getByRole("link", { name: "Download" }));
		await g.caption("Download saves the episode as an MP3");
		await g.hold(1800);
	},
	async after(g) {
		await closeArtifact(g);
		await switchChatModel(g, USUAL_MODEL);
	},
};
