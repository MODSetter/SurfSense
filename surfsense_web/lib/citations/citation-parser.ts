// Pure citation parsing for `[citation:...]` tokens emitted by SurfSense
// agents. No React imports — consumed by both the React renderer
// (markdown surfaces) and the Plate value transform (document viewer).
//
// The same logic previously lived inline in
// `components/assistant-ui/markdown-text.tsx` with module-level mutable
// state. This module exposes a per-call URL map so multiple concurrent
// renderers / SSR contexts can't race each other.

import { FENCED_OR_INLINE_CODE } from "@/lib/markdown/code-regions";

/**
 * Matches `[citation:...]` with numeric IDs (incl. negative, doc- prefix,
 * comma-separated), URL-based IDs from live web search, or `urlciteN`
 * placeholders produced by `preprocessCitationMarkdown`.
 *
 * Also matches Chinese brackets 【】 and zero-width spaces that LLMs
 * sometimes emit.
 */
export const CITATION_REGEX =
	/[[【]\u200B?citation:\s*(https?:\/\/[^\]】\u200B]+|urlcite\d+|(?:doc-)?-?\d+(?:\s*,\s*(?:doc-)?-?\d+)*)\s*\u200B?[\]】]/g;

/** A single parsed citation reference. */
export type CitationToken =
	| { kind: "url"; url: string }
	| { kind: "chunk"; chunkId: number; isDocsChunk: boolean };

/** Output of `parseTextWithCitations` — interleaved text + citation tokens. */
export type ParsedSegment = string | CitationToken;

/** Per-call URL placeholder map; key is `urlciteN`, value is the original URL. */
export type CitationUrlMap = Map<string, string>;

/** Result of preprocessing raw markdown for downstream parsing. */
export interface PreprocessedCitations {
	/** Markdown with `[citation:URL]` tokens rewritten to `[citation:urlciteN]`. */
	content: string;
	/** Lookup table to recover the original URL from each placeholder. */
	urlMap: CitationUrlMap;
}

/** Pattern matching only URL-form citations (used during preprocessing). */
const URL_CITATION_REGEX =
	/[[【]\u200B?citation:\s*(https?:\/\/[^\]】\u200B]+)\s*\u200B?[\]】]/g;

/**
 * Replace `[citation:URL]` tokens with `[citation:urlciteN]` placeholders so
 * GFM autolinks don't split the URL out of the brackets during markdown
 * parsing. Returns both the rewritten content and a map for later lookup.
 *
 * Code-fence aware: skips fenced (``` ``` ```) and inline (`` ` ``) code
 * regions so citation-shaped strings inside example code remain literal.
 *
 * Known limitations: `~~~` fences, 4-space indented code, and LaTeX math
 * blocks are not skipped. Citation tokens inside those regions are rare in
 * practice; documented in the plan.
 */
export function preprocessCitationMarkdown(content: string): PreprocessedCitations {
	const urlMap: CitationUrlMap = new Map();
	let counter = 0;

	// Splitting on a regex with one capture group puts code regions at odd
	// indexes (matched delimiters) and the surrounding text at even indexes.
	// Only transform the even-indexed parts.
	const parts = content.split(FENCED_OR_INLINE_CODE);
	const transformed = parts.map((part, index) => {
		if (index % 2 === 1) return part;
		return part.replace(URL_CITATION_REGEX, (_match, url: string) => {
			const key = `urlcite${counter++}`;
			urlMap.set(key, url.trim());
			return `[citation:${key}]`;
		});
	});

	return { content: transformed.join(""), urlMap };
}

/**
 * Parse a string into an array of plain text segments and citation tokens.
 *
 * Pure data — no React. The renderer module is responsible for mapping
 * tokens to JSX. Negative chunk IDs are forwarded as-is so the consumer
 * can decide how to render anonymous documents.
 */
export function parseTextWithCitations(
	text: string,
	urlMap: CitationUrlMap
): ParsedSegment[] {
	const segments: ParsedSegment[] = [];
	let lastIndex = 0;
	let match: RegExpExecArray | null;

	CITATION_REGEX.lastIndex = 0;
	match = CITATION_REGEX.exec(text);
	while (match !== null) {
		if (match.index > lastIndex) {
			segments.push(text.substring(lastIndex, match.index));
		}

		const captured = match[1];

		if (captured.startsWith("http://") || captured.startsWith("https://")) {
			segments.push({ kind: "url", url: captured.trim() });
		} else if (captured.startsWith("urlcite")) {
			const url = urlMap.get(captured);
			if (url) {
				segments.push({ kind: "url", url });
			}
		} else {
			const rawIds = captured.split(",").map((s) => s.trim());
			for (const rawId of rawIds) {
				const isDocsChunk = rawId.startsWith("doc-");
				const chunkId = Number.parseInt(isDocsChunk ? rawId.slice(4) : rawId, 10);
				if (!Number.isNaN(chunkId)) {
					segments.push({ kind: "chunk", chunkId, isDocsChunk });
				}
			}
		}

		lastIndex = match.index + match[0].length;
		match = CITATION_REGEX.exec(text);
	}

	if (lastIndex < text.length) {
		segments.push(text.substring(lastIndex));
	}

	return segments.length > 0 ? segments : [text];
}

/** Type guard for the citation branch of `ParsedSegment`. */
export function isCitationToken(segment: ParsedSegment): segment is CitationToken {
	return typeof segment !== "string";
}
