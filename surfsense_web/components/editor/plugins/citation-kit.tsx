"use client";

import { type FC } from "react";
import { KEYS, type Descendant } from "platejs";
import { createPlatePlugin, type PlateElementProps } from "platejs/react";
import { InlineCitation, UrlCitation } from "@/components/assistant-ui/inline-citation";
import {
	CITATION_REGEX,
	type CitationUrlMap,
	parseTextWithCitations,
} from "@/lib/citations/citation-parser";

/**
 * Plate inline-void node modeling a single `[citation:...]` reference.
 *
 * Modeled after the existing `MentionPlugin` pattern in
 * `inline-mention-editor.tsx` — the only confirmed pattern in this repo
 * for non-text inline UI. Inline-void elements satisfy Slate's invariant
 * that the editor renders both atomic widgets and surrounding text
 * cleanly without breaking selection / caret semantics.
 */
export type CitationElementNode = {
	type: "citation";
	kind: "chunk" | "doc" | "url";
	chunkId?: number;
	url?: string;
	/** Original `[citation:...]` substring for traceability/debugging. */
	rawText: string;
	children: [{ text: "" }];
};

const CITATION_TYPE = "citation";

const CitationElement: FC<PlateElementProps<CitationElementNode>> = ({
	attributes,
	children,
	element,
}) => {
	const isUrl = element.kind === "url";
	return (
		<span {...attributes} className="inline-flex align-baseline">
			<span contentEditable={false}>
				{isUrl && element.url ? (
					<UrlCitation url={element.url} />
				) : element.chunkId !== undefined ? (
					<InlineCitation chunkId={element.chunkId} isDocsChunk={element.kind === "doc"} />
				) : null}
			</span>
			{children}
		</span>
	);
};

const CitationPlugin = createPlatePlugin({
	key: CITATION_TYPE,
	node: {
		isElement: true,
		isInline: true,
		isVoid: true,
		type: CITATION_TYPE,
		component: CitationElement,
	},
});

/** Plugin kit shape used elsewhere in the editor. */
export const CitationKit = [CitationPlugin];

// ---------------------------------------------------------------------------
// Slate value transform — runs after MarkdownPlugin.deserialize
// ---------------------------------------------------------------------------

// Structural shapes used by the value transform. We cannot use Plate's
// generic Element / Text type predicates directly because `Descendant` is a
// constrained union and our predicates would over-narrow. Casting through
// these row types keeps the walker readable without fighting the types.
type SlateText = { text: string } & Record<string, unknown>;
type SlateElement = { type?: string; children: Descendant[] } & Record<string, unknown>;

function isText(node: Descendant): boolean {
	return typeof (node as { text?: unknown }).text === "string";
}

function asText(node: Descendant): SlateText {
	return node as unknown as SlateText;
}

function asElement(node: Descendant): SlateElement {
	return node as unknown as SlateElement;
}

/**
 * Element types whose subtrees we MUST NOT inject citation void elements
 * into. Each rationale documented in the citation plan:
 *  - `KEYS.codeBlock` / `code_line` — Plate's schema rejects inline elements
 *    inside code containers; the user expects literal text inside code.
 *  - `KEYS.link` — `<button>` inside `<a>` is invalid HTML and the link
 *    swallows the citation click. Mirrors the `<a>` skip in
 *    `MarkdownViewer`.
 */
const SKIP_SUBTREE_TYPES = new Set<string>([
	KEYS.codeBlock,
	"code_line",
	KEYS.link,
]);

/**
 * Build the marks portion of a Slate text node so we can preserve formatting
 * (bold/italic/etc.) on the surrounding text fragments after we split.
 */
function copyMarks(textNode: SlateText): Record<string, unknown> {
	const { text: _text, ...marks } = textNode;
	return marks;
}

function makeCitationElement(
	rawText: string,
	segment: { kind: "url"; url: string } | { kind: "chunk"; chunkId: number; isDocsChunk: boolean }
): CitationElementNode {
	if (segment.kind === "url") {
		return {
			type: CITATION_TYPE,
			kind: "url",
			url: segment.url,
			rawText,
			children: [{ text: "" }],
		};
	}
	return {
		type: CITATION_TYPE,
		kind: segment.isDocsChunk ? "doc" : "chunk",
		chunkId: segment.chunkId,
		rawText,
		children: [{ text: "" }],
	};
}

/**
 * Re-extract the raw `[citation:...]` substrings that produced each parsed
 * segment, in source order. Lets us preserve the original literal for
 * `rawText` on the inline-void element.
 */
function extractRawCitationMatches(text: string): string[] {
	const matches: string[] = [];
	CITATION_REGEX.lastIndex = 0;
	let m: RegExpExecArray | null = CITATION_REGEX.exec(text);
	while (m !== null) {
		matches.push(m[0]);
		m = CITATION_REGEX.exec(text);
	}
	return matches;
}

function transformTextNode(node: SlateText, urlMap: CitationUrlMap): Descendant[] {
	const segments = parseTextWithCitations(node.text, urlMap);
	if (segments.length === 1 && typeof segments[0] === "string") {
		return [node as unknown as Descendant];
	}

	const marks = copyMarks(node);
	const rawMatches = extractRawCitationMatches(node.text);
	const out: Descendant[] = [];
	let citationIdx = 0;
	let pendingText: string | null = null;

	const flushText = () => {
		// Slate inline-void adjacency: emit an empty text node (with copied
		// marks) when the citation appears at the very start/end of the text
		// node so neighbours of the void always have a text sibling.
		out.push({ ...marks, text: pendingText ?? "" } as unknown as Descendant);
		pendingText = null;
	};

	for (const segment of segments) {
		if (typeof segment === "string") {
			pendingText = (pendingText ?? "") + segment;
		} else {
			flushText();
			const raw = rawMatches[citationIdx] ?? "";
			out.push(makeCitationElement(raw, segment) as unknown as Descendant);
			citationIdx += 1;
			// Always reset pendingText so the next loop iteration emits a
			// trailing empty text node if no further plain text follows.
			pendingText = "";
		}
	}
	flushText();

	return out;
}

function transformChildren(children: Descendant[], urlMap: CitationUrlMap): Descendant[] {
	const out: Descendant[] = [];
	for (const child of children) {
		if (isText(child)) {
			out.push(...transformTextNode(asText(child), urlMap));
			continue;
		}
		const elementChild = asElement(child);
		const elementType = (elementChild.type ?? "") as string;
		if (elementType && SKIP_SUBTREE_TYPES.has(elementType)) {
			out.push(child);
			continue;
		}
		out.push({
			...elementChild,
			children: transformChildren(elementChild.children, urlMap),
		} as unknown as Descendant);
	}
	return out;
}

/**
 * Walk a deserialized Slate value and replace every `[citation:...]`
 * substring with a `citation` inline-void element. URL placeholders
 * created by `preprocessCitationMarkdown` are resolved through `urlMap`.
 *
 * Subtrees of `code_block`, `code_line`, and `link` are returned as-is —
 * see `SKIP_SUBTREE_TYPES` above.
 */
export function injectCitationNodes(value: Descendant[], urlMap: CitationUrlMap): Descendant[] {
	return transformChildren(value, urlMap);
}
