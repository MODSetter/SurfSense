import type { PendingInterruptState } from "../approval";

export type QuestionOption = {
	id: string;
	label: string;
	description?: string;
	preview_asset?: string;
};

export type Question = {
	id: string;
	prompt: string;
	input_type: "single_select" | "multi_select" | "free_text";
	presentation: "list" | "visual_cards";
	required: boolean;
	minimum_selections: number;
	maximum_selections: number;
	options: QuestionOption[];
};

export type StructuredQuestionData = {
	type: "structured_question";
	version: 1;
	title: string;
	message?: string;
	origin: { kind: "preset"; preset_id: string; preset_version: number };
	questions: Question[];
};

export const PREVIEW_ASSETS: Record<string, string> = {
	"infographic-style/auto": "/infographic-styles/auto.svg",
	"infographic-style/kawaii": "/infographic-styles/kawaii.svg",
	"infographic-style/clay": "/infographic-styles/clay.svg",
	"infographic-style/sketch-note": "/infographic-styles/sketch-note.svg",
	"infographic-style/anime": "/infographic-styles/anime.svg",
};

export function parseStructuredQuestion(
	value: Record<string, unknown>
): StructuredQuestionData | null {
	if (
		value.type !== "structured_question" ||
		value.version !== 1 ||
		typeof value.title !== "string" ||
		!value.origin ||
		typeof value.origin !== "object" ||
		!Array.isArray(value.questions)
	) {
		return null;
	}
	const origin = value.origin as Record<string, unknown>;
	if (
		origin.kind !== "preset" ||
		typeof origin.preset_id !== "string" ||
		typeof origin.preset_version !== "number"
	) {
		return null;
	}
	const questions: Question[] = [];
	for (const raw of value.questions.slice(0, 8)) {
		if (!raw || typeof raw !== "object") return null;
		const question = raw as Record<string, unknown>;
		if (
			typeof question.id !== "string" ||
			typeof question.prompt !== "string" ||
			!["single_select", "multi_select", "free_text"].includes(String(question.input_type))
		) {
			return null;
		}
		const options = Array.isArray(question.options)
			? question.options.slice(0, 12).flatMap<QuestionOption>((rawOption) => {
					if (!rawOption || typeof rawOption !== "object") return [];
					const option = rawOption as Record<string, unknown>;
					if (typeof option.id !== "string" || typeof option.label !== "string") return [];
					return [
						{
							id: option.id,
							label: option.label,
							...(typeof option.description === "string"
								? { description: option.description }
								: {}),
							...(typeof option.preview_asset === "string" && PREVIEW_ASSETS[option.preview_asset]
								? { preview_asset: option.preview_asset }
								: {}),
						},
					];
				})
			: [];
		questions.push({
			id: question.id,
			prompt: question.prompt,
			input_type: question.input_type as Question["input_type"],
			presentation: question.presentation === "visual_cards" ? "visual_cards" : "list",
			required: question.required !== false,
			minimum_selections:
				typeof question.minimum_selections === "number" ? question.minimum_selections : 1,
			maximum_selections:
				typeof question.maximum_selections === "number" ? question.maximum_selections : 1,
			options,
		});
	}
	return questions.length > 0
		? {
				type: "structured_question",
				version: 1,
				title: value.title,
				...(typeof value.message === "string" ? { message: value.message } : {}),
				origin: {
					kind: "preset",
					preset_id: origin.preset_id,
					preset_version: origin.preset_version,
				},
				questions,
			}
		: null;
}

export function isStructuredQuestionInterrupt(interrupt: PendingInterruptState): boolean {
	return parseStructuredQuestion(interrupt.interruptData) !== null;
}
