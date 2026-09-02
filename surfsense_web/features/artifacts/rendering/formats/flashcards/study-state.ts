import { z } from "zod";
import { FLASHCARDS_MAX_CARDS } from "./schema";

export const FlashcardMarkSchema = z.enum(["good", "again"]);

export const FlashcardStudyStateSchema = z
	.object({
		generation: z.number().int().positive(),
		marks: z.record(z.string(), FlashcardMarkSchema),
		order: z.array(z.number().int().nonnegative()).max(FLASHCARDS_MAX_CARDS),
	})
	.strict();

export type FlashcardMark = z.infer<typeof FlashcardMarkSchema>;
export type FlashcardStudyState = z.infer<typeof FlashcardStudyStateSchema>;

export function normalizeFlashcardStudyState(
	value: unknown,
	generation: number,
	cardCount: number
): FlashcardStudyState {
	const canonicalOrder = Array.from({ length: cardCount }, (_, index) => index);
	const parsed = FlashcardStudyStateSchema.safeParse(value);
	const marks: Record<string, FlashcardMark> = {};
	if (
		parsed.success &&
		parsed.data.generation === generation &&
		parsed.data.order.length === cardCount &&
		parsed.data.order
			.toSorted((left, right) => left - right)
			.every((index, position) => index === position)
	) {
		for (let index = 0; index < cardCount; index += 1) {
			const mark = parsed.data.marks[String(index)];
			if (mark) marks[String(index)] = mark;
		}
		return { generation, marks, order: parsed.data.order };
	}
	return { generation, marks, order: canonicalOrder };
}

export function firstUnseenCard(state: FlashcardStudyState): number {
	for (let position = 0; position < state.order.length; position += 1) {
		if (!state.marks[String(state.order[position])]) return position;
	}
	return 0;
}

export function flashcardProgressCounts(state: FlashcardStudyState, cardCount: number) {
	let remembered = 0;
	let missed = 0;
	for (let index = 0; index < cardCount; index += 1) {
		const mark = state.marks[String(index)];
		if (mark === "good") remembered += 1;
		if (mark === "again") missed += 1;
	}
	return { remembered, missed, unseen: cardCount - remembered - missed };
}
