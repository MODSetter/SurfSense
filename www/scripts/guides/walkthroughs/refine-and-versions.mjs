/** /docs/v2/guides/refine-and-versions: Refine the Word document Studio made, then switch between its versions. */

import { artifactRow, artifactsReady, closeArtifact } from "./studio.mjs";

export const refineAndVersions = {
	slug: "refine-and-versions",
	async before(g) {
		await closeArtifact(g);
	},
	async run(g) {
		const { page } = g;
		// The Word document is the oldest artifact so far: studio-documents made it first.
		const rows = page.getByRole("region", { name: "Artifacts" }).getByRole("listitem");
		await g.click(artifactRow(page, (await rows.count()) - 1), {
			caption: "Open a document Studio made",
		});
		const viewer = page.getByRole("complementary", { name: "Artifact" });
		await viewer.getByRole("document").waitFor();
		await g.click(viewer.getByRole("button", { name: "Refine this document" }), {
			caption: "Click the round Refine button",
		});
		const change = viewer.getByRole("textbox", { name: "How to change this document" });
		await g.type(change, "Shorter: five items, one sentence each", {
			caption: "Describe the change you want",
		});
		await g.hold(600);
		await g.shot("refine-box", { clip: viewer, pad: 0 });
		await page.keyboard.press("Enter");
		await g.waitFor(
			async () => {
				await page.waitForTimeout(3000);
				await artifactsReady(page);
				await viewer.getByRole("button", { name: /^Showing v2/ }).waitFor({ timeout: 600_000 });
			},
			{ caption: "Studio rewrites it into its next version (sped up)" }
		);
		await g.hold(1800);
		await g.shot("version-2", { clip: viewer, pad: 0 });
		await g.noticesGone();
		await g.click(viewer.getByRole("button", { name: /^Showing v2/ }), {
			caption: "Every version stays: pick one to open it",
		});
		await g.hold(1400);
		await g.shot("versions", {
			clip: [viewer.getByRole("button", { name: /^Showing v2/ }), page.getByRole("menu")],
			pad: 16,
		});
		await page.keyboard.press("Escape");
	},
};
