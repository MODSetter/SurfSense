import { z } from "zod";
import { parseStudyText } from "../study-text/parse-text";

export const QUIZ_MAX_VIEWER_BYTES = 15 * 1024 * 1024;
export const QUIZ_MIN_QUESTIONS = 5;
export const QUIZ_MAX_QUESTIONS = 30;

function codePointLength(value: string): number {
	return [...value].length;
}

function hasUnsupportedControlCharacter(value: string): boolean {
	for (const character of value) {
		const codePoint = character.codePointAt(0) ?? 0;
		if (
			codePoint === 0x7f ||
			(codePoint >= 0 && codePoint <= 0x08) ||
			codePoint === 0x0b ||
			codePoint === 0x0c ||
			(codePoint >= 0x0e && codePoint <= 0x1f)
		) {
			return true;
		}
	}
	return false;
}

function boundedStudyText(name: string, maximum: number) {
	return z
		.string()
		.refine((value) => value.trim().length > 0, `${name} must not be empty`)
		.refine((value) => codePointLength(value) <= maximum, `${name} is too long`)
		.refine((value) => !hasUnsupportedControlCharacter(value), `${name} has control characters`)
		.refine((value) => parseStudyText(value) !== null, `${name} has invalid LaTeX delimiters`);
}

function normalizedText(value: string): string {
	let normalized = "";
	let pendingSpace = false;
	for (const character of value.normalize("NFKC").toLocaleLowerCase().trim()) {
		if (character.trim() === "") {
			pendingSpace = normalized.length > 0;
		} else {
			if (pendingSpace) normalized += " ";
			normalized += character;
			pendingSpace = false;
		}
	}
	return normalized;
}

export const QuizQuestionSchema = z
	.object({
		question_text: boundedStudyText("Question", 4_000),
		options: z
			.array(boundedStudyText("Option", 4_000))
			.length(4)
			.refine(
				(options) => new Set(options.map(normalizedText)).size === options.length,
				"Options must be distinct"
			),
		correct_option_index: z.number().int().min(0).max(3),
		explanation_text: boundedStudyText("Explanation", 12_000),
	})
	.strict();

export const QuizSchema = z
	.object({
		schema_version: z.literal(1),
		title: z
			.string()
			.refine((value) => value.trim().length > 0, "Title must not be empty")
			.refine((value) => codePointLength(value) <= 200, "Title is too long")
			.refine(
				(value) =>
					!value.includes("\n") && !value.includes("\r") && !hasUnsupportedControlCharacter(value),
				"Title contains unsupported content"
			),
		questions: z.array(QuizQuestionSchema).min(QUIZ_MIN_QUESTIONS).max(QUIZ_MAX_QUESTIONS),
	})
	.strict()
	.superRefine((quiz, context) => {
		const seen = new Set<string>();
		quiz.questions.forEach((question, index) => {
			const normalized = normalizedText(question.question_text);
			if (seen.has(normalized)) {
				context.addIssue({
					code: "custom",
					path: ["questions", index, "question_text"],
					message: "Duplicate question",
				});
			}
			seen.add(normalized);
		});
	});

export type Quiz = z.infer<typeof QuizSchema>;
