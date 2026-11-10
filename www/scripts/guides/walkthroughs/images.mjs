/**
 * /docs/v2/guides/images: download an image model that draws and edits, draw a
 * picture in Studio, then edit it into its next version. FLUX.2 klein 4B runs
 * on the graphics card; without one, each picture takes minutes.
 */

import { closeSettings, openSettingsSection } from "./open-settings.mjs";
import { artifactRow, artifactsReady, closeArtifact } from "./studio.mjs";

const MODEL = "FLUX.2 klein 4B";

export const images = {
	slug: "images",
	async before(g) {
		await closeArtifact(g);
	},
	async run(g) {
		const { page } = g;
		const settings = await openSettingsSection(g, "Image gen", {
			caption: "Open Settings, then Image gen",
		});
		await g.click(settings.getByRole("button", { name: "Add model" }), {
			caption: "Click Add model",
		});
		const download = settings.getByRole("button", {
			name: new RegExp(`^Download ${MODEL.replace(/\./g, "\\.")}`),
		});
		await download.waitFor();
		await g.hold(1200);
		await g.shot("image-models", { clip: settings });
		await g.click(download, { caption: `Download a model, such as ${MODEL}` });
		const use = settings.getByRole("button", {
			name: new RegExp(`^Use ${MODEL.replace(/\./g, "\\.")}`),
		});
		await g.waitFor(() => use.first().waitFor({ timeout: 900_000 }), {
			caption: "It downloads once (sped up)",
		});
		await g.click(use.first(), { caption: "Click Use" });
		await g.hold(1000);
		await g.click(settings.getByRole("button", { name: "Image edit", exact: true }), {
			caption: "The same model can edit pictures: choose it under Image edit too",
		});
		await g.click(
			settings
				.getByRole("button", { name: new RegExp(`^Use ${MODEL.replace(/\./g, "\\.")}`) })
				.first()
		);
		await g.hold(1200);
		await g.shot("image-edit-model", { clip: settings });
		await closeSettings(g);

		await g.click(
			page
				.getByRole("region", { name: "Studio formats" })
				.getByRole("button", { name: "Image", exact: true }),
			{
				caption: "In Studio, click Image",
			}
		);
		const box = page.getByRole("dialog", { name: "Image" });
		await g.type(
			box.getByRole("textbox"),
			"A flat illustration of a small shop with a padlock on its door, in calm blue and orange",
			{
				caption: "Describe the picture, if you want",
				delay: 14,
			}
		);
		await g.click(box.getByRole("button", { name: "Generate" }), { caption: "Click Generate" });
		await g.waitFor(() => artifactsReady(page), {
			caption: "It draws from your sources and your prompt (sped up)",
		});
		await g.noticesGone();
		await g.click(artifactRow(page, 0), { caption: "Open the picture" });
		const viewer = page.getByRole("complementary", { name: "Artifact" });
		await viewer.getByRole("img").first().waitFor();
		await g.hold(1500);
		await g.shot("picture", { clip: viewer, pad: 0 });

		await g.click(viewer.getByRole("button", { name: "Edit this image" }), {
			caption: "To change it, click the round button",
		});
		await g.type(
			viewer.getByRole("textbox", { name: "How to change this image" }),
			"Make it night time, with warm light in the window",
			{
				caption: "Describe the change",
			}
		);
		await g.shot("edit-box", { clip: viewer, pad: 0 });
		await g.click(viewer.getByRole("button", { name: "Edit", exact: true }), {
			caption: "Click Edit",
		});
		await g.waitFor(
			() => viewer.getByRole("button", { name: /^Showing v2/ }).waitFor({ timeout: 900_000 }),
			{
				caption: "The edit becomes the picture’s next version (sped up)",
			}
		);
		await g.hold(1800);
		await g.shot("edited", { clip: viewer, pad: 0 });
		await g.noticesGone();
	},
};
