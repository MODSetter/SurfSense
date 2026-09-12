import assert from "node:assert/strict";
import test from "node:test";
import { shuffledCardOrder } from "@/features/artifacts/rendering/formats/flashcards/card-order";
import { parseFlashcardText } from "@/features/artifacts/rendering/formats/flashcards/parse-text";
import {
	FLASHCARDS_MIN_CARDS,
	FlashcardDeckSchema,
} from "@/features/artifacts/rendering/formats/flashcards/schema";
import {
	firstUnseenCard,
	flashcardProgressCounts,
	normalizeFlashcardStudyState,
} from "@/features/artifacts/rendering/formats/flashcards/study-state";

function deck(fronts: string[]) {
	return {
		schema_version: 1 as const,
		title: "Compact deck",
		cards: fronts.map((front_text) => ({ front_text, back_text: `Back: ${front_text}` })),
	};
}

test("flashcard text parser segments inline and display math with offsets", () => {
	assert.deepEqual(parseFlashcardText("A \\(x+1\\) B \\[y\\]"), [
		{ type: "text", value: "A ", offset: 0 },
		{ type: "math", value: "x+1", display: false, offset: 2 },
		{ type: "text", value: " B ", offset: 9 },
		{ type: "math", value: "y", display: true, offset: 12 },
	]);
	assert.deepEqual(parseFlashcardText(String.raw`literal \\( text`), [
		{ type: "text", value: String.raw`literal \\( text`, offset: 0 },
	]);
});

test("flashcard text parser rejects malformed delimiters and braces", () => {
	for (const value of ["orphan \\)", "\\(\\)", "\\(x", "\\(x \\[y\\]\\)", "\\({x\\)"]) {
		assert.equal(parseFlashcardText(value), null, value);
	}
});

test("deck schema enforces its minimum and normalized duplicate fronts", () => {
	const validFronts = Array.from({ length: FLASHCARDS_MIN_CARDS }, (_, index) => `Card ${index}`);
	assert.equal(FlashcardDeckSchema.safeParse(deck(validFronts)).success, true);
	assert.equal(FlashcardDeckSchema.safeParse(deck(validFronts.slice(1))).success, false);

	const duplicateFronts = [...validFronts];
	duplicateFronts[0] = "Ａ   TERM";
	duplicateFronts[duplicateFronts.length - 1] = "a term";
	const duplicate = FlashcardDeckSchema.safeParse(deck(duplicateFronts));
	assert.equal(duplicate.success, false);
	if (!duplicate.success) {
		assert.ok(
			duplicate.error.issues.some(
				(issue) =>
					issue.message === "Duplicate card front" &&
					issue.path.join(".") === `cards.${duplicateFronts.length - 1}.front_text`
			)
		);
	}
});

test("study state preserves valid permutations, filters marks, and finds unseen cards", () => {
	const state = normalizeFlashcardStudyState(
		{
			generation: 4,
			marks: { "0": "again", "2": "good", "99": "good" },
			order: [2, 0, 1],
		},
		4,
		3
	);
	assert.deepEqual(state, {
		generation: 4,
		marks: { "0": "again", "2": "good" },
		order: [2, 0, 1],
	});
	assert.deepEqual(flashcardProgressCounts(state, 3), {
		remembered: 1,
		missed: 1,
		unseen: 1,
	});
	assert.equal(firstUnseenCard(state), 2);
	assert.equal(firstUnseenCard({ ...state, marks: { "0": "again", "1": "good", "2": "good" } }), 0);
});

test("study state resets stale generations and invalid permutations", () => {
	assert.deepEqual(
		normalizeFlashcardStudyState({ generation: 1, marks: { "0": "good" }, order: [0, 0, 2] }, 2, 3),
		{ generation: 2, marks: {}, order: [0, 1, 2] }
	);
});

test("shuffle is deterministic for an injected random source and remains a permutation", () => {
	const values = [0, 0.5, 0.9];
	const shuffled = shuffledCardOrder(4, () => values.shift() ?? 0);
	assert.deepEqual(shuffled, [3, 2, 1, 0]);
	assert.deepEqual(
		shuffled.toSorted((left, right) => left - right),
		[0, 1, 2, 3]
	);
});
