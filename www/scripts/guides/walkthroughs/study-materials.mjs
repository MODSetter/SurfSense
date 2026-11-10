/** /docs/v2/guides/study-materials: flashcards, a quiz and a mind map from the same sources, made at once. */

import {
	artifactRow,
	artifacts,
	artifactsReady,
	clearArtifacts,
	closeArtifact,
	generate,
} from "./studio.mjs";

const PROMPT = "The key ideas to remember, not publication numbers or dates";

async function start(g, format, prompt) {
	const box = await generate(g, format, { caption: `Click ${format}` });
	if (prompt)
		await g.type(box.getByRole("textbox"), prompt, {
			caption: "Steer it with a prompt",
			delay: 14,
		});
	await g.click(box.getByRole("button", { name: "Generate" }), { caption: "Click Generate" });
}

export const studyMaterials = {
	slug: "study-materials",
	/** Keeps the Word document studio-documents made, which refine-and-versions refines. */
	async prepare({ apiUrl }) {
		await clearArtifacts(apiUrl, { keep: 1 });
	},
	async before(g) {
		await closeArtifact(g);
	},
	async run(g) {
		const { page } = g;
		await start(g, "Flashcards", PROMPT);
		await start(g, "Quiz", PROMPT);
		await start(g, "Mind map");
		await g.caption("Start several at once: each appears under Artifacts");
		await g.hold(1500);
		await g.shot("three-at-once", { clip: artifacts(page) });
		await g.waitFor(() => artifactsReady(page), { caption: "They’re made side by side (sped up)" });

		// Newest first: the mind map, then the quiz, then the flashcards.
		await g.click(artifactRow(page, 2), { caption: "Open the flashcards" });
		const viewer = page.getByRole("complementary", { name: "Artifact" });
		const reveal = viewer.getByRole("button", { name: "Reveal answer" });
		await reveal.waitFor();
		await g.hold(1500);
		await g.shot("flashcard", { clip: viewer, pad: 0 });
		await g.click(reveal, { caption: "Click See answer to turn the card over" });
		await g.hold(1500);
		await g.shot("flashcard-answer", { clip: viewer, pad: 0 });
		await g.click(viewer.getByRole("button", { name: /^Got it/ }), {
			caption: "Mark it Got it or Needs review",
		});
		await g.hold(1000);

		// An open artifact takes the Artifacts list's place: close it to reach the next one.
		await closeArtifact(g);
		await g.click(artifactRow(page, 1), { caption: "Open the quiz" });
		const firstAnswer = viewer.getByRole("radio").first();
		await firstAnswer.waitFor();
		await g.hold(1200);
		await g.click(firstAnswer, {
			caption: "Pick an answer: the quiz marks it and shows the right one",
		});
		await g.hold(2000);
		await g.shot("quiz", { clip: viewer, pad: 0 });

		await closeArtifact(g);
		await g.click(artifactRow(page, 0), { caption: "Open the mind map" });
		await viewer.getByRole("list", { name: "Mind map" }).waitFor();
		await g.click(viewer.getByRole("button", { name: "Fit mind map" }), {
			caption: "Fit mind map shows all of it",
		});
		await g.hold(2000);
		await g.shot("mind-map");
	},
};
