import type { MentionedDocumentInfo } from "@/atoms/chat/mentioned-documents.atom";

export type MentionSegment =
	| { type: "text"; value: string; start: number }
	| { type: "mention"; doc: MentionedDocumentInfo; start: number };

/**
 * Tokenizes a user message into text and `@mention` segments.
 *
 * Pure: no React, no DOM, no side effects. Safe to unit-test and reuse.
 *
 * Mentions are matched greedily by longest title first so that a longer title
 * (e.g. `@Project Roadmap`) is never shadowed by a shorter prefix
 * (e.g. `@Project`).
 */
export function parseMentionSegments(
	text: string,
	docs: ReadonlyArray<MentionedDocumentInfo>
): MentionSegment[] {
	if (text.length === 0) return [];
	if (docs.length === 0) return [{ type: "text", value: text, start: 0 }];

	const tokens = docs
		.map((doc) => ({ doc, token: `@${doc.title}` }))
		.sort((a, b) => b.token.length - a.token.length);

	const segments: MentionSegment[] = [];
	let i = 0;
	let buffer = "";
	let bufferStart = 0;

	while (i < text.length) {
		const tokenMatch = tokens.find(({ token }) => text.startsWith(token, i));
		if (tokenMatch) {
			if (buffer) {
				segments.push({ type: "text", value: buffer, start: bufferStart });
				buffer = "";
			}
			segments.push({ type: "mention", doc: tokenMatch.doc, start: i });
			i += tokenMatch.token.length;
			bufferStart = i;
			continue;
		}
		if (!buffer) bufferStart = i;
		buffer += text[i];
		i += 1;
	}

	if (buffer) {
		segments.push({ type: "text", value: buffer, start: bufferStart });
	}

	return segments;
}
