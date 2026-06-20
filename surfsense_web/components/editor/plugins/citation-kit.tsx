"use client";

import { type Descendant, KEYS } from "platejs";
import { createPlatePlugin, type PlateElementProps } from "platejs/react";
import type { FC } from "react";
import { InlineCitation, LineCitation, UrlCitation } from "@/components/assistant-ui/inline-citation";
import {
	CITATION_REGEX,
	type CitationToken,
	type CitationUrlMap,
	parseTextWithCitations,
} from "@/lib/citations/citation-parser";

/**
 * Plate inline-void node for one `[citation:...]` reference.
 * Inline voids keep the citation chip atomic while preserving caret behavior
 * around the surrounding text.
 */
export type CitationElementNode = {
	type: "citation";
	kind: "chunk" | "doc" | "url" | "line";
	chunkId?: number;
	url?: string;
	documentId?: number;
	startLine?: number;
	endLine?: number;
	/** Original literal token that produced this citation node. */
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
	const isLine =
		element.kind === "line" &&
		element.documentId !== undefined &&
		element.startLine !== undefined &&
		element.endLine !== undefined;
	return (
		<span {...attributes} className="inline-flex align-baseline">
			<span contentEditable={false}>
				{isUrl && element.url ? (
					<UrlCitation url={element.url} />
				) : isLine ? (
					<LineCitation
						documentId={element.documentId as number}
						startLine={element.startLine as number}
						endLine={element.endLine as number}
					/>
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

export const CitationKit = [CitationPlugin];

// ---------------------------------------------------------------------------
// Slate value transform
// ---------------------------------------------------------------------------

// Local structural shapes keep the recursive walker readable without forcing
// Plate's broad Descendant union into narrower generic predicates.
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
 * Subtrees that should keep citation tokens as text:
 * - Code nodes preserve source text and reject inline void children.
 * - Link nodes already render as anchors; citation chips are interactive
 *   shadcn Button-based controls, so injecting them would nest interactions.
 */
const SKIP_SUBTREE_TYPES = new Set<string>([KEYS.codeBlock, "code_line", KEYS.link]);

/**
 * Preserve text marks such as bold and italic when splitting around citations.
 */
function copyMarks(textNode: SlateText): Record<string, unknown> {
	const { text: _text, ...marks } = textNode;
	return marks;
}

function makeCitationElement(rawText: string, segment: CitationToken): CitationElementNode {
	if (segment.kind === "url") {
		return {
			type: CITATION_TYPE,
			kind: "url",
			url: segment.url,
			rawText,
			children: [{ text: "" }],
		};
	}
	if (segment.kind === "line") {
		return {
			type: CITATION_TYPE,
			kind: "line",
			documentId: segment.documentId,
			startLine: segment.startLine,
			endLine: segment.endLine,
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
 * Keep each original citation token on the generated node for diagnostics.
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
		// Inline voids need text siblings, even at text boundaries.
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
			// Ensure a trailing text sibling if the citation ends the node.
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
 * Replace citation tokens in a deserialized Slate tree with citation inline
 * void nodes. URL placeholders from `preprocessCitationMarkdown` are resolved
 * through `urlMap`; skipped subtrees are returned unchanged.
 */
export function injectCitationNodes(value: Descendant[], urlMap: CitationUrlMap): Descendant[] {
	return transformChildren(value, urlMap);
}
