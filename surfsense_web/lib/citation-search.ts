/**
 * Snippet generation for the citation-jump highlight, driven by Plate's
 * `FindReplacePlugin`. The plugin runs `decorate` per-block and only matches
 * within blocks whose children are all `Text` nodes (so it crosses inline
 * marks like bold/italic but **not** block boundaries, and a block that
 * contains even one inline element such as a link is silently skipped).
 * That means a full chunk that spans heading + paragraph won't match as a
 * single string — we have to pick a shorter snippet that fits inside one
 * rendered block.
 *
 * `buildCitationSearchCandidates` returns search strings ordered from
 * "most-specific anchor" to "broadest fallback":
 *   1. First sentence of the chunk (capped at `FIRST_SENTENCE_MAX`).
 *   2. First `FIRST_PHRASE_WORDS` words.
 *   3. Each non-trivial line of the chunk, in source order — gives us a
 *      separate attempt for each rendered block, so a heading line with
 *      an inline link doesn't doom the whole jump.
 *   4. Full chunk (only if it's already short enough to plausibly fit
 *      inside one block).
 *
 * The caller tries each candidate in turn — set the plugin's `search`
 * option, `editor.api.redecorate()`, then check the editor DOM for a
 * `.citation-highlight-leaf` element. First candidate that produces one
 * wins; subsequent candidates are skipped.
 */

const FIRST_SENTENCE_MAX = 120;
const FIRST_PHRASE_WORDS = 8;
const MIN_SNIPPET_LENGTH = 6;
const FULL_CHUNK_MAX = FIRST_SENTENCE_MAX * 2;
const MAX_LINE_CANDIDATES = 6;
const LINE_CANDIDATE_MAX = FIRST_SENTENCE_MAX;

function normalizeWhitespace(input: string): string {
	return input.replace(/\s+/g, " ").trim();
}

/**
 * Strip the markdown syntax that won't survive into the rendered editor's
 * plain text, so the chunk text (which comes back from the indexer as raw
 * source markdown) can be matched against the literal text values stored
 * in Plate's Slate tree.
 *
 * Order matters: handle multi-char and "container" syntax before single-
 * char emphasis, otherwise `**text**` collapses to `*text*` first.
 *
 * Heuristic only — we don't aim to be a full markdown parser, just to
 * remove the common markers (`**bold**`, `[text](url)`, `# headings`,
 * `- list`, etc.) that show up in connector-doc chunks and would break
 * literal substring search.
 */
export function stripMarkdownForMatch(input: string): string {
	let s = input;
	s = s.replace(/```[a-z0-9_+-]*\n?([\s\S]*?)```/gi, (_, body: string) => body);
	s = s.replace(/<!--[\s\S]*?-->/g, " ");
	s = s.replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1");
	s = s.replace(/!\[([^\]]*)\]\[[^\]]*\]/g, "$1");
	s = s.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1");
	s = s.replace(/\[([^\]]+)\]\[[^\]]*\]/g, "$1");
	s = s.replace(/<((?:https?|mailto):[^>\s]+)>/g, "$1");
	s = s.replace(/`+([^`\n]+?)`+/g, "$1");
	s = s.replace(/(\*\*|__)([\s\S]+?)\1/g, "$2");
	s = s.replace(/(?<!\w)([*_])([^*_\n]+?)\1(?!\w)/g, "$2");
	s = s.replace(/~~([^~]+)~~/g, "$1");
	s = s.replace(/^[ \t]{0,3}#{1,6}[ \t]+/gm, "");
	s = s.replace(/^[ \t]{0,3}(?:=+|-+)[ \t]*$/gm, "");
	s = s.replace(/^[ \t]{0,3}>+[ \t]?/gm, "");
	s = s.replace(/^[ \t]*[-*+][ \t]+/gm, "");
	s = s.replace(/^[ \t]*\d+\.[ \t]+/gm, "");
	s = s.replace(/^[ \t]{0,3}(?:[-*_])(?:[ \t]*[-*_]){2,}[ \t]*$/gm, "");
	s = s.replace(/^[ \t]*\|?(?:[ \t]*:?-+:?[ \t]*\|)+[ \t]*:?-+:?[ \t]*\|?[ \t]*$/gm, "");
	s = s.replace(/\\([\\`*_{}[\]()#+\-.!~>])/g, "$1");
	return s;
}

export function buildCitationSearchCandidates(rawText: string): string[] {
	if (!rawText) return [];
	const stripped = stripMarkdownForMatch(rawText);
	const normalized = normalizeWhitespace(stripped);
	if (normalized.length < MIN_SNIPPET_LENGTH) return [];

	const out: string[] = [];
	const seen = new Set<string>();
	const push = (s: string) => {
		const t = normalizeWhitespace(s);
		if (t.length >= MIN_SNIPPET_LENGTH && !seen.has(t)) {
			out.push(t);
			seen.add(t);
		}
	};

	const sentenceMatch = normalized.match(/^[^.!?]+[.!?]/);
	if (sentenceMatch) {
		const sentence = sentenceMatch[0];
		push(sentence.length > FIRST_SENTENCE_MAX ? sentence.slice(0, FIRST_SENTENCE_MAX) : sentence);
	} else if (normalized.length > FIRST_SENTENCE_MAX) {
		push(normalized.slice(0, FIRST_SENTENCE_MAX));
	}

	const words = normalized.split(" ").filter(Boolean);
	if (words.length > FIRST_PHRASE_WORDS) {
		push(words.slice(0, FIRST_PHRASE_WORDS).join(" "));
	}

	// Per-line candidates: each chunk line is roughly one block in the
	// rendered editor. Trying them in order gives us a separate decorate
	// attempt for each block, which matters when the first line is a
	// heading containing a link (Plate's `FindReplacePlugin` will skip
	// any block whose children aren't all text nodes).
	const rawLines = stripped.split(/\r?\n/);
	let lineCount = 0;
	for (const line of rawLines) {
		if (lineCount >= MAX_LINE_CANDIDATES) break;
		const trimmed = normalizeWhitespace(line);
		if (trimmed.length < MIN_SNIPPET_LENGTH) continue;
		push(trimmed.length > LINE_CANDIDATE_MAX ? trimmed.slice(0, LINE_CANDIDATE_MAX) : trimmed);
		lineCount++;
	}

	if (normalized.length <= FULL_CHUNK_MAX) {
		push(normalized);
	}

	return out;
}
