import { z } from "zod";

export const FLASHCARDS_MAX_VIEWER_BYTES = 15 * 1024 * 1024;
export const FLASHCARDS_MIN_CARDS = 2;
export const FLASHCARDS_MAX_CARDS = 100;

const UNSUPPORTED_MARKDOWN =
	/<[^>\n]+>|!\[[^\]]*\](?:\([^)]*\)|\[[^\]]*\])|(?<!!)\[[^\]]+\](?:\([^)]*\)|\[[^\]]*\])|^\s*\[[^\]]+\]:\s*\S+|^\s{0,3}#{1,6}(?:\s+|$)|^\s*(?:=+|-+)\s*$/m;

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

function boundedText(name: string, maximum: number) {
	return z
		.string()
		.refine((value) => value.trim().length > 0, `${name} must not be empty`)
		.refine((value) => codePointLength(value) <= maximum, `${name} is too long`)
		.refine((value) => !hasUnsupportedControlCharacter(value), `${name} has control characters`)
		.refine((value) => !UNSUPPORTED_MARKDOWN.test(value), `${name} has unsupported Markdown`);
}

export const FlashcardSchema = z
	.object({
		front_markdown: boundedText("Front", 4_000),
		back_markdown: boundedText("Back", 12_000),
		hint_markdown: boundedText("Hint", 2_000).optional(),
	})
	.strict();

export const FlashcardDeckSchema = z
	.object({
		schema_version: z.literal(1),
		title: z
			.string()
			.refine((value) => value.trim().length > 0, "Title must not be empty")
			.refine((value) => codePointLength(value) <= 200, "Title is too long")
			.refine(
				(value) =>
					!value.includes("\n") &&
					!value.includes("\r") &&
					!hasUnsupportedControlCharacter(value) &&
					!/<[^>\n]+>/.test(value),
				"Title contains unsupported content"
			),
		cards: z.array(FlashcardSchema).min(FLASHCARDS_MIN_CARDS).max(FLASHCARDS_MAX_CARDS),
	})
	.strict()
	.superRefine((deck, context) => {
		const seen = new Set<string>();
		deck.cards.forEach((card, index) => {
			const normalized = card.front_markdown
				.normalize("NFKC")
				.toLocaleLowerCase()
				.trim()
				.replace(/\s+/g, " ");
			if (seen.has(normalized)) {
				context.addIssue({
					code: "custom",
					path: ["cards", index, "front_markdown"],
					message: "Duplicate card front",
				});
			}
			seen.add(normalized);
		});
	});

export const FlashcardMarkSchema = z.enum(["good", "again"]);

export const FlashcardProgressResponseSchema = z
	.object({
		generation: z.number().int().positive(),
		marks: z.record(z.string(), FlashcardMarkSchema),
	})
	.strict();

export type FlashcardDeck = z.infer<typeof FlashcardDeckSchema>;
export type FlashcardMark = z.infer<typeof FlashcardMarkSchema>;
export type FlashcardProgress = z.infer<typeof FlashcardProgressResponseSchema>;

export function normalizeFlashcardProgress(
	value: unknown,
	generation: number,
	cardCount: number
): FlashcardProgress {
	const parsed = FlashcardProgressResponseSchema.safeParse(value);
	const marks: Record<string, FlashcardMark> = {};
	if (parsed.success && parsed.data.generation === generation) {
		for (let index = 0; index < cardCount; index += 1) {
			const mark = parsed.data.marks[String(index)];
			if (mark) marks[String(index)] = mark;
		}
	}
	return { generation, marks };
}

export function firstUnseenCard(progress: FlashcardProgress, cardCount: number): number {
	for (let index = 0; index < cardCount; index += 1) {
		if (!progress.marks[String(index)]) return index;
	}
	return 0;
}

export function flashcardProgressCounts(progress: FlashcardProgress, cardCount: number) {
	let remembered = 0;
	let missed = 0;
	for (let index = 0; index < cardCount; index += 1) {
		const mark = progress.marks[String(index)];
		if (mark === "good") remembered += 1;
		if (mark === "again") missed += 1;
	}
	return { remembered, missed, unseen: cardCount - remembered - missed };
}
