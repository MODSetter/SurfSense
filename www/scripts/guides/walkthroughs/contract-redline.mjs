/**
 * /docs/v2/guides/contract-redline: review a contract you received against
 * your playbook with the contract redline job, then read the marked-up copy in
 * Studio. The contract is a real NDA from an SEC filing (ContractNLI); the
 * playbook is the Bonterms Mutual NDA, standing in for a firm's own standard
 * agreement. It runs on Claude Sonnet 5.5: on Haiku 5.5 the job wrote stray
 * markup into its changes in both of two runs (10 Nov 2026), so a take whose
 * copy holds any is refused rather than published.
 */

import { join } from "node:path";

import { sourcesPanel, sourcesReady } from "./add-sources.mjs";
import { deleteSources } from "./agent-chat.mjs";
import { switchChatModel } from "./chat-model.mjs";
import { closeArtifact, deleteArtifactsTitled } from "./studio.mjs";
import { answerAsTrial } from "./trial-license.mjs";

const CONTRACT = "Confidentiality and non-disclosure agreement.docx";
const PLAYBOOK = "Bonterms Mutual NDA.pdf";
const REDLINE_MODEL = "anthropic/claude-sonnet-5.5";
// What a model's formatting leaves behind; the contract itself has none of it.
const LEAKED_MARKUP = /[{}<>]|\]\(|\[\.\.\.\]|\(\.\.\.\)/;

/** Room for the page and its comments: the sidebar goes, and Studio widens as far as it goes. */
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
	await page.mouse.move(300, y, { steps: 16 });
	await page.mouse.up();
	await page.waitForTimeout(800);
}

export const contractRedline = {
	slug: "contract-redline",
	// The comments sit beside the page, which needs Studio at its widest.
	viewport: { width: 1440, height: 900 },
	// The larger window makes a larger poster: this keeps it near the others' size.
	posterQuality: 62,
	async intercept({ page, apiUrl }) {
		await answerAsTrial(page, apiUrl);
	},
	/** An earlier take's sources and marked-up copies, so the run starts with none. */
	async prepare({ apiUrl }) {
		await deleteSources(apiUrl, [CONTRACT, PLAYBOOK]);
		await deleteArtifactsTitled(apiUrl, "Confidentiality and non-disclosure agreement");
	},
	async before(g) {
		await closeArtifact(g);
		await switchChatModel(g, REDLINE_MODEL);
	},
	async run(g) {
		const { page } = g;
		const panel = sourcesPanel(page);
		await g.click(panel.getByRole("button", { name: "Add sources" }), {
			caption: "Add the contract you received, and your playbook, to Sources",
		});
		const chooser = page.waitForEvent("filechooser");
		await g.click(page.getByRole("menuitem", { name: "Upload files…" }));
		await (await chooser).setFiles([
			join(g.docsDir, "Contracts", CONTRACT),
			join(g.docsDir, "Firm playbook", PLAYBOOK),
		]);
		await panel.getByRole("treeitem", { name: PLAYBOOK }).waitFor({ timeout: 120_000 });
		await g.waitFor(() => sourcesReady(page, 300_000), {
			caption: "A playbook is your positions, your own standard agreement, or both",
		});
		await g.hold(1000);

		const sidebar = page
			.getByRole("complementary")
			.filter({ has: page.getByRole("heading", { name: "SurfSense" }) });
		await g.click(sidebar.getByRole("button", { name: /^Jobs/ }), {
			caption: "Open Jobs, in the sidebar",
		});
		const jobs = page.getByRole("dialog", { name: "Jobs" });
		const run = jobs.getByRole("button", { name: "Run Contract redline" });
		await run.waitFor();
		await g.hold(1600);
		await g.click(run, { caption: "Click Run beside Contract redline" });

		await jobs.getByRole("heading", { name: "Contract to review" }).waitFor();
		await g.caption("It marks up a copy of the contract: your file stays as it is");
		await g.hold(2200);
		await g.click(jobs.getByRole("button", { name: "Deselect all" }), {
			caption: "Tick your playbook’s documents",
		});
		await g.click(jobs.getByRole("checkbox", { name: PLAYBOOK }));
		await g.hold(1600);
		await g.shot("run-form", { clip: jobs });
		// The form's foot names the model that reviews, which the top of the form leaves out.
		const start = jobs.getByRole("button", { name: "Start", exact: true });
		await g.point(start);
		await g.caption("The form names the model that reviews");
		await g.hold(2000);
		await g.shot("start", { clip: jobs });
		await g.click(start, { caption: "Click Start" });

		await jobs
			.getByRole("status")
			.filter({ hasText: /\d+ of \d+ review points/ })
			.waitFor({ timeout: 180_000 });
		await g.caption("It checks the contract one review point at a time");
		await g.hold(1200);
		await g.shot("progress", { clip: jobs });
		await g.waitFor(
			() => jobs.getByRole("button", { name: "Open in Studio" }).waitFor({ timeout: 900_000 }),
			{ caption: "Each change has to rest on your playbook (sped up)" }
		);
		await g.caption("Then it says what it changed, and what already meets your playbook");
		await g.hold(2400);
		await g.shot("done", { clip: jobs });

		await g.click(jobs.getByRole("button", { name: "Open in Studio" }), {
			caption: "Open the marked-up copy in Studio",
		});
		const viewer = page.getByRole("complementary", { name: "Artifact" });
		const document = viewer.getByRole("document");
		await document.waitFor();
		await g.noticesGone();
		const text = await document.innerText();
		const leak = text.match(LEAKED_MARKUP);
		if (leak) {
			const at = text.indexOf(leak[0]);
			throw new Error(
				`contract-redline: markup in the copy, near “${text.slice(Math.max(0, at - 60), at + 10)}”; retake`
			);
		}
		await widenStudio(g);
		// Small enough that a whole line and its comment fit side by side.
		for (let step = 0; step < 3; step++) {
			await g.click(viewer.getByRole("button", { name: "Zoom out" }), { caption: "" });
		}
		// The first change, in the middle of the view: its comment's marker, after the summary's on the title.
		await document
			.getByRole("button", { name: /^Comment \d+$/ })
			.nth(1)
			.evaluate((marker) => marker.scrollIntoView({ block: "center" }));
		await page.waitForTimeout(800);
		const box = await document.boundingBox();
		await page.mouse.move(box.x + box.width / 3, box.y + box.height / 3, { steps: 6 });
		await g.caption("Each change is a tracked change, with a comment beside it");
		// The comments sit to the right of the page: scroll across to them.
		await page.mouse.wheel(400, 0);
		await g.hold(2600);
		await g.shot("redline", { clip: viewer, pad: 0, quality: 72 });
		await g.point(viewer.getByRole("link", { name: "With changes" }));
		await g.caption("Download it with changes, or clean, once you’ve checked it");
		await g.hold(2200);
	},
};
