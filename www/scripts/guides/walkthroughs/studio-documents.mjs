/** /docs/v2/guides/studio-documents: a Word document from the ticked sources, opened in Studio's viewer. */

import {
	artifactRow,
	artifacts,
	artifactsReady,
	clearArtifacts,
	closeArtifact,
	generate,
} from "./studio.mjs";

export const studioDocuments = {
	slug: "studio-documents",
	/** The Studio walkthroughs count on an Artifacts list that starts empty. */
	async prepare({ apiUrl }) {
		await clearArtifacts(apiUrl);
	},
	async before(g) {
		await closeArtifact(g);
	},
	async run(g) {
		const { page } = g;
		const box = await generate(g, "Word", { caption: "In Studio, click a format, such as Word" });
		await g.hold(900);
		await g.shot("format-box", { clip: box });
		await g.click(box.getByRole("button", { name: /sources$/ }), {
			caption: "Choose the sources it uses",
		});
		await g.hold(1000);
		await g.shot("choose-sources", { clip: box });
		await g.click(box.getByRole("button", { name: /^Sources \(/ }), { caption: "" });
		await g.type(
			box.getByRole("textbox"),
			"A one-page checklist a small business can follow to start on cybersecurity",
			{
				caption: "Write a prompt to steer it, if you want",
				delay: 18,
			}
		);
		await g.click(box.getByRole("button", { name: "Generate" }), { caption: "Click Generate" });
		await g.caption("It appears under Artifacts while it’s made");
		await g.hold(1500);
		await g.shot("generating", { clip: artifacts(page) });
		await g.waitFor(() => artifactsReady(page), {
			caption: "Your chat model writes it from your sources (sped up)",
		});

		await g.click(artifactRow(page, 0), { caption: "Click it to open it" });
		const viewer = page.getByRole("complementary", { name: "Artifact" });
		await viewer.getByRole("document").waitFor();
		await g.hold(2000);
		await g.shot("word-viewer");
		await g.noticesGone();
		await g.point(viewer.getByRole("link", { name: "Download" }));
		await g.caption("Download saves the Word file, to open in Word or LibreOffice");
		await g.hold(2200);
	},
};
