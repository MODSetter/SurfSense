import { z } from "zod";
import type { Quiz } from "./schema";
import { QUIZ_MAX_QUESTIONS } from "./schema";

export const QuizStateSchema = z
	.object({
		generation: z.number().int().positive(),
		mode: z.enum(["all", "missed"]),
		active_question_indices: z.array(z.number().int().nonnegative()).max(QUIZ_MAX_QUESTIONS),
		answers: z.record(z.string(), z.number().int().min(0).max(3)),
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
	return { ...parsed.data, answers };
}

export function quizRunComplete(state: QuizState): boolean {
	return state.active_question_indices.every((index) => state.answers[String(index)] !== undefined);
}

export function firstUnansweredPosition(state: QuizState): number {
	const position = state.active_question_indices.findIndex(
		(index) => state.answers[String(index)] === undefined
	);
	return position < 0 ? 0 : position;
}

export function quizResults(quiz: Quiz, state: QuizState) {
	const missed: number[] = [];
	let correct = 0;
	quiz.questions.forEach((question, index) => {
		if (state.answers[String(index)] === question.correct_option_index) correct += 1;
		else missed.push(index);
	});
	return {
		correct,
		missed,
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

export function retakeLocalQuiz(quiz: Quiz, state: QuizState, mode: QuizRetakeMode): QuizState {
	if (mode === "all") return emptyQuizState(state.generation, quiz.questions.length);
	const { missed } = quizResults(quiz, state);
	const answers = { ...state.answers };
	for (const index of missed) delete answers[String(index)];
	return {
		generation: state.generation,
		mode: "missed",
		active_question_indices: missed,
		answers,
	};
}
