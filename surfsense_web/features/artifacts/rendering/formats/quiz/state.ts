import { z } from "zod";
import type { Quiz } from "./schema";
import { QUIZ_MAX_QUESTIONS } from "./schema";

export const QuizStateSchema = z
	.object({
		generation: z.number().int().positive(),
		mode: z.enum(["all", "missed"]),
		active_question_indices: z.array(z.number().int().nonnegative()).max(QUIZ_MAX_QUESTIONS),
		answers: z.record(z.string(), z.number().int().min(0).max(3)),
		skipped_question_indices: z.array(z.number().int().nonnegative()).max(QUIZ_MAX_QUESTIONS),
	})
	.strict();

export type QuizState = z.infer<typeof QuizStateSchema>;
export type QuizRetakeMode = QuizState["mode"];

export function emptyQuizState(generation: number, questionCount: number): QuizState {
	return {
		generation,
		mode: "all",
		active_question_indices: Array.from({ length: questionCount }, (_, index) => index),
		answers: {},
		skipped_question_indices: [],
	};
}

export function normalizeQuizState(
	value: unknown,
	generation: number,
	questionCount: number
): QuizState {
	const parsed = QuizStateSchema.safeParse(value);
	if (!parsed.success || parsed.data.generation !== generation) {
		return emptyQuizState(generation, questionCount);
	}
	const scope = parsed.data.active_question_indices;
	const validScope =
		scope.length > 0 &&
		scope.every(
			(index, position) => index < questionCount && (position === 0 || scope[position - 1] < index)
		);
	const canonical =
		parsed.data.mode !== "all" ||
		(scope.length === questionCount && scope.every((index, position) => index === position));
	if (!validScope || !canonical) return emptyQuizState(generation, questionCount);

	const answers: Record<string, number> = {};
	for (let index = 0; index < questionCount; index += 1) {
		const answer = parsed.data.answers[String(index)];
		if (answer !== undefined) answers[String(index)] = answer;
	}
	const skipped = parsed.data.skipped_question_indices;
	const validSkipped = skipped.every(
		(index, position) =>
			index < questionCount &&
			(position === 0 || skipped[position - 1] < index) &&
			answers[String(index)] === undefined
	);
	return validSkipped
		? { ...parsed.data, answers, skipped_question_indices: skipped }
		: emptyQuizState(generation, questionCount);
}

export function quizRunComplete(state: QuizState): boolean {
	const skipped = new Set(state.skipped_question_indices);
	return state.active_question_indices.every(
		(index) => state.answers[String(index)] !== undefined || skipped.has(index)
	);
}

export function firstUnansweredPosition(state: QuizState): number {
	const skipped = new Set(state.skipped_question_indices);
	const position = state.active_question_indices.findIndex(
		(index) => state.answers[String(index)] === undefined && !skipped.has(index)
	);
	return position < 0 ? 0 : position;
}

export function quizResults(quiz: Quiz, state: QuizState) {
	const missed: number[] = [];
	const skipped: number[] = [];
	const skippedSet = new Set(state.skipped_question_indices);
	let correct = 0;
	quiz.questions.forEach((question, index) => {
		if (skippedSet.has(index)) skipped.push(index);
		else if (state.answers[String(index)] === question.correct_option_index) correct += 1;
		else missed.push(index);
	});
	return {
		correct,
		missed,
		skipped,
		total: quiz.questions.length,
		percentage: Math.round((correct / quiz.questions.length) * 100),
	};
}

export function submitLocalAnswer(
	state: QuizState,
	questionIndex: number,
	selectedOptionIndex: number
): QuizState {
	return {
		...state,
		answers: { ...state.answers, [String(questionIndex)]: selectedOptionIndex },
	};
}

export function skipLocalQuestion(state: QuizState, questionIndex: number): QuizState {
	return {
		...state,
		skipped_question_indices: [
			...new Set([...state.skipped_question_indices, questionIndex]),
		].toSorted((a, b) => a - b),
	};
}

export function retakeLocalQuiz(quiz: Quiz, state: QuizState, mode: QuizRetakeMode): QuizState {
	if (mode === "all") return emptyQuizState(state.generation, quiz.questions.length);
	const result = quizResults(quiz, state);
	const missed = [...result.missed, ...result.skipped].toSorted((a, b) => a - b);
	const answers = { ...state.answers };
	for (const index of missed) delete answers[String(index)];
	return {
		generation: state.generation,
		mode: "missed",
		active_question_indices: missed,
		answers,
		skipped_question_indices: [],
	};
}
