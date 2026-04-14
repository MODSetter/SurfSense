// ---------------------------------------------------------------------------
// MDX pre-processing helpers
// ---------------------------------------------------------------------------
// remarkMdx treats { } as JSX expression delimiters and does NOT support
// HTML comments (<!-- -->). Arbitrary markdown from document conversions
// (e.g. PDF-to-markdown via Azure/DocIntel) can contain constructs that
// break the MDX parser. This module sanitises them before deserialization.
// ---------------------------------------------------------------------------

const FENCED_OR_INLINE_CODE = /(```[\s\S]*?```|`[^`\n]+`)/g;

// Strip HTML comments that MDX cannot parse.
// PDF converters emit <!-- PageHeader="..." -->, <!-- PageBreak -->, etc.
// MDX uses JSX-style comments and chokes on HTML comments, causing the
// parser to stop at the first occurrence.
// - <!-- PageBreak --> becomes a thematic break (---)
// - All other HTML comments are removed
function stripHtmlComments(md: string): string {
	return md
		.replace(/<!--\s*PageBreak\s*-->/gi, "\n---\n")
		.replace(/<!--[\s\S]*?-->/g, "");
}

// Convert <figure>...</figure> blocks to plain text blockquotes.
// <figure> with arbitrary text content is not valid JSX, causing the MDX
// parser to fail.
function convertFigureBlocks(md: string): string {
	return md.replace(/<figure[^>]*>([\s\S]*?)<\/figure>/gi, (_match, inner: string) => {
		const trimmed = (inner as string).trim();
		if (!trimmed) return "";
		const quoted = trimmed
			.split("\n")
			.map((line) => `> ${line}`)
			.join("\n");
		return `\n${quoted}\n`;
	});
}

// Escape unescaped { and } outside of fenced/inline code so remarkMdx
// treats them as literal characters rather than JSX expression delimiters.
function escapeCurlyBraces(md: string): string {
	const parts = md.split(FENCED_OR_INLINE_CODE);

	return parts
		.map((part, i) => {
			if (i % 2 === 1) return part;
			return part.replace(/(?<!\\)\{/g, "\\{").replace(/(?<!\\)\}/g, "\\}");
		})
		.join("");
}

// Pre-process raw markdown so it can be safely parsed by the MDX-enabled
// Plate editor. Applies all sanitisation steps in order.
export function escapeMdxExpressions(md: string): string {
	let result = md;
	result = stripHtmlComments(result);
	result = convertFigureBlocks(result);
	result = escapeCurlyBraces(result);
	return result;
}
