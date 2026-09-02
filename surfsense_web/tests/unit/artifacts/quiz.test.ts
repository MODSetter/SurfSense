import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { QuizSchema } from "@/features/artifacts/rendering/formats/quiz/schema";
import {
	emptyQuizState,
	normalizeQuizState,
	quizResults,
	quizRunComplete,
	retakeLocalQuiz,
	skipLocalQuestion,
	submitLocalAnswer,
} from "@/features/artifacts/rendering/formats/quiz/state";

function quiz() {
	return {
		schema_version: 1 as const,
		title: "Compact quiz",
		questions: Array.from({ length: 5 }, (_, index) => ({
			question_text: `Question ${index}`,
			options: ["A", "B", "C", "D"].map((option) => `${option} ${index}`),
			correct_option_index: index % 4,
			explanation_text: `Explanation ${index}`,
		})),
	};
}

test("quiz schema requires five questions and exactly four distinct options", () => {
	assert.equal(QuizSchema.safeParse(quiz()).success, true);
	assert.equal(
		QuizSchema.safeParse({ ...quiz(), questions: quiz().questions.slice(1) }).success,
		false
	);
	const duplicate = quiz();
	duplicate.questions[0].options = ["Same", " same ", "C", "D"];
	assert.equal(QuizSchema.safeParse(duplicate).success, false);
});

test("quiz state normalizes, completes, scores, and retakes missed questions", () => {
	const deck = quiz();
	let state = normalizeQuizState(undefined, 2, deck.questions.length);
	assert.deepEqual(state, emptyQuizState(2, 5));
	for (let index = 0; index < deck.questions.length; index += 1) {
		state = submitLocalAnswer(state, index, index === 1 ? 3 : index % 4);
	}
	assert.equal(quizRunComplete(state), true);
	assert.deepEqual(quizResults(deck, state), {
		correct: 4,
		missed: [1],
		skipped: [],
		total: 5,
		percentage: 80,
	});
	const missed = retakeLocalQuiz(deck, state, "missed");
	assert.deepEqual(missed.active_question_indices, [1]);
	assert.equal(missed.answers["1"], undefined);
	const all = retakeLocalQuiz(deck, state, "all");
	assert.deepEqual(all, emptyQuizState(2, 5));
});

test("skipped questions complete a run and join the missed retake scope", () => {
	const deck = quiz();
	let state = emptyQuizState(2, 5);
	for (let index = 0; index < 4; index += 1) {
		state = submitLocalAnswer(state, index, index % 4);
	}
	state = skipLocalQuestion(state, 4);

	assert.equal(quizRunComplete(state), true);
	assert.deepEqual(quizResults(deck, state), {
		correct: 4,
		missed: [],
		skipped: [4],
		total: 5,
		percentage: 80,
	});
	assert.deepEqual(retakeLocalQuiz(deck, state, "missed").active_question_indices, [4]);
});

test("viewer keeps quiz interactions semantic, accessible, and local for public manifests", () => {
	const source = readFileSync("features/artifacts/rendering/formats/quiz/quiz-viewer.tsx", "utf8");
	const score = readFileSync("features/artifacts/rendering/formats/quiz/score-screen.tsx", "utf8");

	assert.match(source, /<RadioGroup/);
	assert.match(source, /aria-label="Quiz progress"/);
	assert.match(source, /data-vaul-no-drag/);
	assert.match(source, /bg-sidebar/);
	assert.match(source, /text-sidebar-foreground/);
	assert.match(source, /manifest\.quiz_state !== undefined/);
	assert.match(source, /persisted\s*\?\s*await submitAnswer/);
	assert.match(source, /:\s*submitLocalAnswer/);
	assert.match(source, /onValueChange=\{\(value\) => void selectAnswer/);
	assert.match(source, /selectedOption === null \? "" : String\(selectedOption\)/);
	assert.match(source, /border-green-500/);
	assert.match(source, /border-red-500/);
	assert.match(source, /"View score" : "Next"/);
	assert.match(source, /useSkipQuizQuestion/);
	assert.match(source, /skipLocalQuestion/);
	assert.match(source, /: "Skip"/);
	assert.match(source, /className="relative w-28/);
	assert.match(source, /savingQuestion \? "opacity-0"/);
	assert.match(source, /<Spinner size="sm" className="absolute"/);
	assert.doesNotMatch(source, /Submit answer/);
	assert.match(score, /Retake missed questions/);
	assert.match(score, /Retake all questions/);
	assert.match(score, /\{correct\} correct/);
	assert.match(score, /\{missed\.length\} missed/);
	assert.match(score, /\{skipped\.length\} skipped/);
	assert.match(score, /<Dot/);
	assert.match(score, /useState<ResultCategory>\("missed"\)/);
	assert.match(score, /<Tabs[\s\S]*value=\{category\}/);
	assert.match(score, /onClick=\{\(\) => setCategory\("correct"\)\}/);
	assert.match(score, /onClick=\{\(\) => setCategory\("missed"\)\}/);
	assert.match(score, /onClick=\{\(\) => setCategory\("skipped"\)\}/);
	assert.match(score, /category === "correct" && "border-white"/);
	assert.match(score, /category === "missed" && "border-white"/);
	assert.match(score, /h-72 overflow-y-auto/);
	assert.match(score, /value="correct"/);
	assert.match(score, /value="missed"/);
	assert.match(score, /title="Correct"/);
	assert.match(score, /title="Missed"/);
	assert.match(score, /title="Skipped"/);
	assert.match(score, /onClick=\{\(\) => onReview\(index\)\}/);
	assert.match(source, /setReviewIndex\(index\)/);
	assert.match(score, /inline-flex items-center gap-2 opacity-0/);
	assert.match(score, /<Spinner size="sm" className="absolute"/);
	assert.doesNotMatch(score, /Got it|Missed it/);
	assert.doesNotMatch(`${source}\n${score}`, /shuffle|download|multi-select/i);
});
