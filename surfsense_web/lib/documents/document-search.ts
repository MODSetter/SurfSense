export type MatchRange = readonly [start: number, end: number];

export interface TextMatch {
	score: number;
	ranges: MatchRange[];
}

interface NormalizedText {
	value: string;
	starts: number[];
	ends: number[];
}

const DIACRITICS = /\p{Diacritic}/gu;

function normalizeWithOffsets(text: string): NormalizedText {
	let value = "";
	const starts: number[] = [];
	const ends: number[] = [];
	let offset = 0;

	for (const character of text) {
		const normalized = character.normalize("NFD").replace(DIACRITICS, "").toLowerCase();
		for (const normalizedCharacter of normalized) {
			value += normalizedCharacter;
			starts.push(offset);
			ends.push(offset + character.length);
		}
		offset += character.length;
	}

	return { value, starts, ends };
}

function mergeRanges(indices: number[], text: NormalizedText): MatchRange[] {
	const ranges: MatchRange[] = [];

	for (const index of indices) {
		const start = text.starts[index];
		const end = text.ends[index];
		const previous = ranges.at(-1);

		if (previous && start <= previous[1]) {
			ranges[ranges.length - 1] = [previous[0], Math.max(previous[1], end)];
		} else {
			ranges.push([start, end]);
		}
	}

	return ranges;
}

export function matchText(query: string, text: string): TextMatch | null {
	const normalizedQuery = normalizeWithOffsets(query.trim()).value;
	if (!normalizedQuery) return null;

	const normalizedText = normalizeWithOffsets(text);
	const contiguousIndex = normalizedText.value.indexOf(normalizedQuery);

	if (contiguousIndex >= 0) {
		const indices = Array.from(
			{ length: normalizedQuery.length },
			(_, index) => contiguousIndex + index
		);
		const isPrefix = contiguousIndex === 0;
		const isWordBoundary =
			isPrefix || /[\s/_.-]/.test(normalizedText.value[contiguousIndex - 1] ?? "");

		return {
			score: (isPrefix ? 3000 : isWordBoundary ? 2500 : 2000) - contiguousIndex,
			ranges: mergeRanges(indices, normalizedText),
		};
	}

	// ponytail: Greedy subsequence matching intentionally favors a compact,
	// predictable local search. Replace with uFuzzy if typo/transposition
	// tolerance becomes a product requirement.
	const indices: number[] = [];
	let queryIndex = 0;
	for (let textIndex = 0; textIndex < normalizedText.value.length; textIndex++) {
		if (normalizedText.value[textIndex] !== normalizedQuery[queryIndex]) continue;
		indices.push(textIndex);
		queryIndex++;
		if (queryIndex === normalizedQuery.length) break;
	}

	if (queryIndex !== normalizedQuery.length) return null;

	const span = indices[indices.length - 1] - indices[0] + 1;
	return {
		score: 1000 - span - indices[0],
		ranges: mergeRanges(indices, normalizedText),
	};
}
