/** /docs/v2/guides/set-up: from the welcome screen to the first workspace. Needs a new install. */

/** The setup card, from its heading to its bottom bar. */
function card(page, heading, button) {
	return {
		clip: [
			page.getByRole("heading", { name: heading }),
			page.getByRole("button", { name: button, exact: true }),
		],
		pad: 28,
	};
}

export const setUp = {
	slug: "set-up",
	async run(g) {
		const { page } = g;
		await g.caption("Open SurfSense for the first time");
		await g.hold(1200);
		await g.shot("welcome", {
			clip: [
				page.getByRole("heading", { level: 1 }),
				page.getByRole("button", { name: "Start setting up" }),
			],
			pad: 56,
			quality: 72,
		});
		await g.click(page.getByRole("button", { name: "Start setting up" }));

		await page.getByRole("heading", { name: "Privacy choices" }).waitFor();
		await g.caption("Answer Yes or No to each privacy choice");
		await g.click(
			page.getByRole("group", { name: "Check for updates" }).getByRole("button", { name: "Yes" })
		);
		await g.click(
			page
				.getByRole("group", { name: "Share usage statistics" })
				.getByRole("button", { name: "Yes" })
		);
		await g.shot("privacy-choices", card(page, "Privacy choices", "Continue"));
		await g.click(page.getByRole("button", { name: "Continue" }));

		await page.getByRole("heading", { name: "Choose a text generation model" }).waitFor();
		await g.caption("Pick a model to run on this computer");
		await g.hold(1500);
		await g.shot("text-model", card(page, "Choose a text generation model", "Continue"));
		const smallest = page.getByRole("button", { name: "Download Qwen3 0.6B UD-Q4_K_XL" });
		await g.click(smallest, { caption: "Click Download beside the model you want" });
		const ask = page.getByRole("alertdialog");
		await ask.waitFor();
		await g.caption("SurfSense asks before it downloads anything");
		await g.hold(1200);
		await g.shot("allow-download", { clip: ask });
		await g.click(ask.getByRole("button", { name: "Allow" }));
		await g.waitFor(
			() => page.getByRole("region", { name: "Model ready" }).waitFor({ timeout: 600_000 }),
			{
				caption: "The model downloads, then it’s in use (sped up)",
			}
		);
		await g.caption("The model is ready");
		await g.hold(1200);
		await g.shot("model-ready", card(page, "Choose a text generation model", "Continue"));
		await g.click(page.getByRole("button", { name: "Continue" }));

		await page.getByRole("heading", { name: "Choose an embedding model" }).waitFor();
		await g.caption("Keep the default embedding model, or pick a multilingual one");
		await g.hold(1500);
		await g.shot("embedding-model", card(page, "Choose an embedding model", "Finish"));
		await g.click(page.getByRole("button", { name: "Finish", exact: true }));

		await page.getByRole("textbox", { name: "Message" }).waitFor();
		await g.caption("Your first workspace is ready");
		await g.hold(1800);
		await g.shot("first-workspace");
	},
};
