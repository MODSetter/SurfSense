import { z } from "zod";

export const FLASHCARDS_MAX_VIEWER_BYTES = 15 * 1024 * 1024;
// Published schema versions are immutable read contracts. Add a separate V2
// schema and dispatch by schema_version for incompatible changes.
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

function isEscaped(value: string, index: number): boolean {
	let precedingBackslashes = 0;
	for (let cursor = index - 1; cursor >= 0 && value[cursor] === "\\"; cursor -= 1) {
		precedingBackslashes += 1;
	}
	return precedingBackslashes % 2 === 1;
}

function hasBalancedLatexBraces(value: string): boolean {
	let depth = 0;
	for (let index = 0; index < value.length; index += 1) {
		if (isEscaped(value, index)) continue;
		if (value[index] === "{") depth += 1;
		if (value[index] === "}") depth -= 1;
		if (depth < 0) return false;
	}
	return depth === 0;
}

export type FlashcardTextSegment =
	| { type: "text"; value: string; offset: number }
	| { type: "math"; value: string; display: boolean; offset: number };

export function parseFlashcardText(value: string): FlashcardTextSegment[] | null {
	const segments: FlashcardTextSegment[] = [];
	let textStart = 0;
	let index = 0;
	while (index < value.length) {
		const delimiter = value.slice(index, index + 2);
		if ((delimiter === "\\)" || delimiter === "\\]") && !isEscaped(value, index)) {
			return null;
		}
		if ((delimiter !== "\\(" && delimiter !== "\\[") || isEscaped(value, index)) {
			index += 1;
			continue;
		}

		if (index > textStart) {
			segments.push({ type: "text", value: value.slice(textStart, index), offset: textStart });
		}
		const openingOffset = index;
		const display = delimiter === "\\[";
		const closing = display ? "\\]" : "\\)";
		const latexStart = index + 2;
		index = latexStart;
		while (index < value.length) {
			const candidate = value.slice(index, index + 2);
			if ((candidate === "\\(" || candidate === "\\[") && !isEscaped(value, index)) {
				return null;
			}
			if ((candidate === "\\)" || candidate === "\\]") && !isEscaped(value, index)) {
				if (candidate !== closing) return null;
				const latex = value.slice(latexStart, index);
				if (!latex.trim() || !hasBalancedLatexBraces(latex)) return null;
				segments.push({ type: "math", value: latex, display, offset: openingOffset });
				index += 2;
				textStart = index;
				break;
			}
			index += 1;
		}
		if (textStart !== index) return null;
	}
	if (textStart < value.length) {
		segments.push({ type: "text", value: value.slice(textStart), offset: textStart });
	}
	return segments;
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
