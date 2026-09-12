import assert from "node:assert/strict";
import test from "node:test";
import { parseStructuredQuestion } from "@/features/chat-messages/hitl/questions/structured-question-contract";

const payload = {
	type: "structured_question",
	version: 1,
	title: "Choose a style",
	origin: {
		kind: "preset",
		preset_id: "infographic.visual-style",
		preset_version: 1,
	},
	questions: [
		{
			id: "visual-style",
			prompt: "Which style?",
			input_type: "single_select",
			presentation: "visual_cards",
			required: true,
			minimum_selections: 1,
			maximum_selections: 1,
			options: [
				{
					id: "kawaii",
					label: "Kawaii",
					description: "Friendly rounded forms.",
					preview_asset: "infographic-style/kawaii",
				},
			],
		},
	],
} satisfies Record<string, unknown>;

test("parses a bounded visual-card structured question", () => {
	const parsed = parseStructuredQuestion(payload);

	assert.equal(parsed?.origin.preset_id, "infographic.visual-style");
	assert.equal(parsed?.questions[0]?.presentation, "visual_cards");
	assert.equal(parsed?.questions[0]?.options[0]?.preview_asset, "infographic-style/kawaii");
});

test("drops non-allowlisted preview assets without dropping the option", () => {
	const unsafe = structuredClone(payload);
	unsafe.questions[0].options[0].preview_asset = "https://example.com/tracker.png";

	const parsed = parseStructuredQuestion(unsafe);

	assert.equal(parsed?.questions[0]?.options.length, 1);
	assert.equal(parsed?.questions[0]?.options[0]?.preview_asset, undefined);
});

test("rejects unknown variants and malformed origins", () => {
	assert.equal(parseStructuredQuestion({ ...payload, type: "approval" }), null);
	assert.equal(
		parseStructuredQuestion({
			...payload,
			origin: { kind: "agent", preset_id: "x", preset_version: 1 },
		}),
		null
	);
});
