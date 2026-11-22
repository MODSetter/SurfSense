/** /docs/v2/guides/local-model: download a chat model in Settings › Text gen and run it on this computer. */

import { closeSettings, openSettingsSection } from "./open-settings.mjs";

export const localModel = {
	slug: "local-model",
	async run(g) {
		const settings = await openSettingsSection(g, "Text gen", {
			caption: "Open Settings, then Text gen",
		});
		await g.shot("text-gen", { clip: settings });
		await g.click(settings.getByRole("button", { name: "Add model" }), {
			caption: "Click Add model",
		});

		const onThisComputer = settings.getByRole("region", { name: "On this computer" });
		await onThisComputer.waitFor();
		await onThisComputer.scrollIntoViewIfNeeded();
		await g.caption("SurfSense checks what fits this computer");
		await g.hold(1600);
		await g.shot("fits-this-computer", { clip: settings });

		const pick = onThisComputer.getByRole("article").filter({ hasText: "Qwen3 1.7B" });
		const download = pick.getByRole("button", { name: /^Download/ }).first();
		await g.click(download, { caption: "Click Download on the model you want" });
		await g.waitFor(
			() =>
				pick
					.getByRole("button", { name: /^(In use|Use)\b/ })
					.first()
					.waitFor({ timeout: 900_000 }),
			{ caption: "It downloads on this computer (sped up)" }
		);
		const use = pick.getByRole("button", { name: /^Use\b/ });
		if (await use.count()) await g.click(use.first(), { caption: "Click Use" });
		await g.caption("The model runs on this computer");
		await g.hold(1500);
		await g.shot("downloaded", { clip: pick, pad: 16 });
		await closeSettings(g);
	},
};
