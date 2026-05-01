"use client";

import type { ReactNode } from "react";
import { InlineCitation, UrlCitation } from "@/components/assistant-ui/inline-citation";
import {
	type CitationToken,
	type CitationUrlMap,
	parseTextWithCitations,
} from "@/lib/citations/citation-parser";

/**
 * Render a single parsed citation token as JSX.
 *
 * `ordinalKey` should be a stable per-render counter so duplicate identical
 * citations within the same parent don't collide on `key`. The previous
 * implementation in `markdown-text.tsx` used the source string itself as
 * the key, which produced React warnings when two segments rendered the
 * same `[citation:N]` text.
 */
export function renderCitationToken(token: CitationToken, ordinalKey: number): ReactNode {
	if (token.kind === "url") {
		return <UrlCitation key={`citation-url-${ordinalKey}`} url={token.url} />;
	}
	return (
		<InlineCitation
			key={`citation-${token.isDocsChunk ? "doc-" : ""}${token.chunkId}-${ordinalKey}`}
			chunkId={token.chunkId}
			isDocsChunk={token.isDocsChunk}
		/>
	);
}

/**
 * Walk a `ReactNode` (string, array, or arbitrary node) and replace any
 * `[citation:...]` tokens inside string children with citation badges.
 *
 * Designed for use inside `Streamdown`/`react-markdown` `components`
 * overrides where the renderer hands you `children`. Non-string children
 * are returned untouched so block/phrasing structure is preserved.
 */
export function processChildrenWithCitations(
	children: ReactNode,
	urlMap: CitationUrlMap
): ReactNode {
	if (typeof children === "string") {
		const segments = parseTextWithCitations(children, urlMap);
		if (segments.length === 1 && typeof segments[0] === "string") {
			return children;
		}
		let ordinal = 0;
		return segments.map((segment) =>
			typeof segment === "string" ? segment : renderCitationToken(segment, ordinal++)
		);
	}

	if (Array.isArray(children)) {
		let ordinal = 0;
		return children.map((child, childIndex) => {
			if (typeof child === "string") {
				const segments = parseTextWithCitations(child, urlMap);
				if (segments.length === 1 && typeof segments[0] === "string") {
					return child;
				}
				return (
					<span key={`citation-seg-${childIndex}`}>
						{segments.map((segment) =>
							typeof segment === "string"
								? segment
								: renderCitationToken(segment, ordinal++)
						)}
					</span>
				);
			}
			return child;
		});
	}

	return children;
}
