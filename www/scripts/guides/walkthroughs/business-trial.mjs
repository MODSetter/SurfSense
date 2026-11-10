/**
 * /docs/v2/guides/business-trial: Settings › License with no license, the trial
 * link, then adding the license file the trial email brings, and the jobs it
 * downloads. The file is a placeholder: the walkthrough answers the license
 * routes as the trial would (see trial-license.mjs).
 */

import { writeFileSync } from "node:fs";
import { join } from "node:path";

import { setHostAllowed } from "./egress.mjs";
import { closeSettings, openSettingsSection } from "./open-settings.mjs";
import { closeArtifact } from "./studio.mjs";
import { answerAsTrial } from "./trial-license.mjs";

const FILE_NAME = "surfsense.lic";
const PLACEHOLDER = [
	"-----BEGIN LICENSE FILE-----",
	Buffer.from("Not a license: the guide capture answers for it.").toString("base64"),
	"-----END LICENSE FILE-----",
	"",
].join("\n");

export const businessTrial = {
	slug: "business-trial",
	async intercept({ page, apiUrl }) {
		await answerAsTrial(page, apiUrl, { licensed: false });
	},
	/** Off again, so the take shows the question the first jobs download asks. */
	async prepare({ apiUrl }) {
		await setHostAllowed(apiUrl, "api.surfsense.com", false);
	},
	async before(g) {
		await closeArtifact(g);
	},
	async run(g) {
		const { page } = g;
		const settings = await openSettingsSection(g, "License", {
			caption: "Open Settings, then License",
		});
		await settings.getByText("No license on this device").waitFor();
		await g.hold(1400);
		await g.shot("no-license", { clip: settings });
		await g.point(settings.getByRole("link", { name: /^Start a free trial/ }));
		await g.caption("Start a free trial opens SurfSense’s site: the trial comes by email");
		await g.hold(2600);

		await g.click(settings.getByRole("button", { name: "Add license" }), {
			caption: "The license file comes by email: save it, then click Add license",
		});
		const dialog = page.getByRole("dialog", { name: "Add license" });
		await dialog.waitFor();
		await g.hold(1200);
		await g.shot("add-license", { clip: dialog });
		const file = join(g.scratchDir, FILE_NAME);
		writeFileSync(file, PLACEHOLDER);
		// The hidden file input carries the same name, and Chromium counts it a button: the visible one is last.
		const [picker] = await Promise.all([
			page.waitForEvent("filechooser"),
			g.click(dialog.getByRole("button", { name: "Choose license file" }).last(), {
				caption: "Choose the .lic file, or paste it",
			}),
		]);
		await picker.setFiles(file);

		const ask = page.getByRole("alertdialog", { name: "Allow downloading your jobs?" });
		await ask.waitFor();
		await g.caption("SurfSense asks before it downloads the jobs your license includes");
		await g.hold(2400);
		// No margin: Settings › License sits close behind the question.
		await g.shot("allow-jobs", { clip: ask, pad: 0 });
		await g.click(ask.getByRole("button", { name: "Allow" }));
		await page
			.locator("[data-sonner-toast]")
			.filter({ hasText: "Security questionnaire is ready to run" })
			.waitFor();
		await g.caption("The trial is active, and its jobs are on this computer");
		await g.hold(2000);
		await g.shot("active", { clip: settings });
		await closeSettings(g);

		const sidebar = page
			.getByRole("complementary")
			.filter({ has: page.getByRole("heading", { name: "SurfSense" }) });
		await g.click(sidebar.getByRole("button", { name: /^Jobs/ }), {
			caption: "Run them from Jobs, in the sidebar",
		});
		const jobs = page.getByRole("dialog", { name: "Jobs" });
		await jobs.getByRole("button", { name: "Run Security questionnaire" }).waitFor();
		await g.hold(2400);
		await g.click(jobs.getByRole("button", { name: "Close" }).last(), { caption: "" });
	},
};
