/**
 * /docs/v2/guides/security-questionnaire: fill in a supplier security
 * questionnaire (the NCSC's questions, in a workbook from a made-up customer)
 * from a firm's written security plan (the IRS sample WISP, already a source),
 * then open the filled-in copy in Studio. It runs on Claude Haiku 5.5, as the
 * agent guides do, under the trial license trial-license.mjs answers with.
 */

import { join } from "node:path";

import { sourcesPanel, sourcesReady } from "./add-sources.mjs";
import { AGENT_MODEL, deleteSources } from "./agent-chat.mjs";
import { switchChatModel } from "./chat-model.mjs";
import { closeArtifact, deleteArtifactsTitled } from "./studio.mjs";
import { answerAsTrial } from "./trial-license.mjs";

const WORKBOOK = "Supplier security questionnaire.xlsx";
const POLICY = "Written Information Security Plan.docx";

/** The sheet needs the room: the sidebar goes, and the Studio panel widens as far as it goes. */
async function widenStudio(g) {
	const { page } = g;
	await g.click(page.getByRole("button", { name: "Hide sidebar" }), {
		caption: "Hide the sidebar and widen Studio to read it",
	});
	const handle = page.getByRole("separator", { name: "Resize right panel" });
	const box = await handle.boundingBox();
	const y = box.y + box.height / 2;
	await page.mouse.move(box.x + box.width / 2, y, { steps: 8 });
	await page.waitForTimeout(400);
	await page.mouse.down();
	await page.mouse.move(360, y, { steps: 16 });
	await page.mouse.up();
	await page.waitForTimeout(600);
}

export const securityQuestionnaire = {
	slug: "security-questionnaire",
	async intercept({ page, apiUrl }) {
		await answerAsTrial(page, apiUrl);
	},
	/** An earlier take's workbook and every job's copies, so the run starts with none and Recent runs is empty. */
	async prepare({ apiUrl }) {
		await deleteSources(apiUrl, [WORKBOOK]);
		await deleteArtifactsTitled(apiUrl, "Supplier security questionnaire");
		await deleteArtifactsTitled(apiUrl, "Confidentiality and non-disclosure agreement");
	},
	async before(g) {
		await closeArtifact(g);
		await switchChatModel(g, AGENT_MODEL);
	},
	async run(g) {
		const { page } = g;
		const panel = sourcesPanel(page);
		await g.click(panel.getByRole("button", { name: "Add sources" }), {
			caption: "Add the questionnaire you received to Sources",
		});
		const chooser = page.waitForEvent("filechooser");
		await g.click(page.getByRole("menuitem", { name: "Upload files…" }));
		await (await chooser).setFiles(join(g.docsDir, "Questionnaires", WORKBOOK));
		await panel.getByRole("treeitem", { name: WORKBOOK }).waitFor({ timeout: 120_000 });
		await g.waitFor(() => sourcesReady(page, 300_000), {
			caption: "Your policies are sources too",
		});
		await g.hold(1000);

		const sidebar = page
			.getByRole("complementary")
			.filter({ has: page.getByRole("heading", { name: "SurfSense" }) });
		await g.click(sidebar.getByRole("button", { name: /^Jobs/ }), {
			caption: "Open Jobs, in the sidebar",
		});
		const jobs = page.getByRole("dialog", { name: "Jobs" });
		const run = jobs.getByRole("button", { name: "Run Security questionnaire" });
		await run.waitFor();
		await g.hold(1800);
		await g.shot("jobs", { clip: jobs });
		await g.click(run, { caption: "Click Run beside Security questionnaire" });

		await jobs.getByRole("heading", { name: "Workbook to fill in" }).waitFor();
		await g.caption("It fills in a copy of the workbook: your file stays as it is");
		await g.hold(2200);
		await g.click(jobs.getByRole("button", { name: "Deselect all" }), {
			caption: "Tick the documents the answers should rest on",
		});
		await g.click(jobs.getByRole("checkbox", { name: POLICY }));
		await g.hold(1600);
		await g.shot("run-form", { clip: jobs });
		// The form's foot names the model that answers, which the top of the form leaves out.
		const start = jobs.getByRole("button", { name: "Start", exact: true });
		await g.point(start);
		await g.caption("The form names the model that answers");
		await g.hold(2000);
		await g.shot("start", { clip: jobs });
		await g.click(start, { caption: "Click Start" });

		await jobs
			.getByRole("status")
			.filter({ hasText: /\d+ of \d+ questions/ })
			.waitFor({ timeout: 180_000 });
		await g.caption("Jobs shows how far it has got");
		await g.hold(1200);
		await g.shot("progress", { clip: jobs });
		await g.waitFor(
			() => jobs.getByRole("button", { name: "Open in Studio" }).waitFor({ timeout: 900_000 }),
			{ caption: "Each answer has to rest on a passage in your documents (sped up)" }
		);
		await g.caption("Then it says what it answered, and what needs a person");
		await g.hold(2400);
		await g.shot("done", { clip: jobs });

		await g.click(jobs.getByRole("button", { name: "Open in Studio" }), {
			caption: "Open the filled-in copy in Studio",
		});
		const viewer = page.getByRole("complementary", { name: "Artifact" });
		const answers = viewer.getByRole("button", { name: "Questionnaire", exact: true });
		await answers.waitFor();
		await g.noticesGone();
		await widenStudio(g);
		await g.click(answers, { caption: "Each answer is in its cell, with its source beside it" });
		await g.click(viewer.getByRole("button", { name: "Zoom out" }));
		await g.click(viewer.getByRole("button", { name: "Zoom out" }));
		const sheet = viewer.getByRole("region", { name: /^Spreadsheet viewport/ });
		await g.point(sheet);
		await page.mouse.wheel(120, 0);
		await g.hold(2400);
		await g.shot("answers", { clip: viewer, pad: 0, quality: 80 });
		await g.click(viewer.getByRole("button", { name: "SurfSense exceptions" }), {
			caption: "What it couldn’t back is listed for a person to check",
		});
		await g.hold(2400);
		await g.shot("exceptions", { clip: viewer, pad: 0, quality: 80 });
	},
};
