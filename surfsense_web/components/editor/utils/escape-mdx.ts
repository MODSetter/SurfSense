// ---------------------------------------------------------------------------
// MDX curly-brace escaping helper
// ---------------------------------------------------------------------------
// remarkMdx treats { } as JSX expression delimiters. Arbitrary markdown
// (e.g. AI-generated reports) can contain curly braces that are NOT valid JS
// expressions, which makes acorn throw "Could not parse expression".
// We escape unescaped { and } *outside* of fenced code blocks and inline code
// so remarkMdx treats them as literal characters while still parsing
// <mark>, <u>, <kbd>, etc. tags correctly.
// ---------------------------------------------------------------------------

const FENCED_OR_INLINE_CODE = /(```[\s\S]*?```|`[^`\n]+`)/g;

export function escapeMdxExpressions(md: string): string {
	const parts = md.split(FENCED_OR_INLINE_CODE);

	return parts
		.map((part, i) => {
			// Odd indices are code blocks / inline code – leave untouched
			if (i % 2 === 1) return part;
			// Escape { and } that are NOT already escaped (no preceding \)
			return part.replace(/(?<!\\)\{/g, "\\{").replace(/(?<!\\)\}/g, "\\}");
		})
		.join("");
}
