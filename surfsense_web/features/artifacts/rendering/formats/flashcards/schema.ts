import { z } from "zod";
import { parseFlashcardText } from "./parse-text";

export const FLASHCARDS_MAX_VIEWER_BYTES = 15 * 1024 * 1024;
export const FLASHCARDS_MIN_CARDS = 15;
export const FLASHCARDS_MAX_CARDS = 100;

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
		.refine((value) => parseFlashcardText(value) !== null, `${name} has invalid LaTeX delimiters`);
}

function normalizeRecallTarget(value: string): string {
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

export const FlashcardSchema = z
	.object({
		front_text: boundedText("Front", 4_000),
		back_text: boundedText("Back", 12_000),
		hint_text: boundedText("Hint", 2_000).optional(),
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
					!value.includes("\n") && !value.includes("\r") && !hasUnsupportedControlCharacter(value),
				"Title contains unsupported content"
			),
		cards: z.array(FlashcardSchema).min(FLASHCARDS_MIN_CARDS).max(FLASHCARDS_MAX_CARDS),
	})
	.strict()
	.superRefine((deck, context) => {
		const seen = new Set<string>();
		deck.cards.forEach((card, index) => {
			const normalized = normalizeRecallTarget(card.front_text);
			if (seen.has(normalized)) {
				context.addIssue({
					code: "custom",
					path: ["cards", index, "front_text"],
					message: "Duplicate card front",
				});
			}
			seen.add(normalized);
		});
	});

export type FlashcardDeck = z.infer<typeof FlashcardDeckSchema>;
