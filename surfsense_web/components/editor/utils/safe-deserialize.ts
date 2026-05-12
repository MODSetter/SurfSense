// ---------------------------------------------------------------------------
// Safe markdown deserialization for the Plate editor
// ---------------------------------------------------------------------------
// `remark-mdx` treats any HTML-like tag as JSX, so unbalanced inline HTML
// (very common in GitHub READMEs, web-scraped pages, PDF conversions) makes
// it throw "Expected a closing tag for `<a>`" and crash the editor.
//
// Per the MDX maintainers' guidance (mdx-js/mdx, ipikuka/next-mdx-remote-client
// #14), MDX is the wrong format for untrusted markdown and the recommended
// fix is to fall back to plain markdown parsing. `MarkdownPlugin.deserialize`
// accepts a per-call `remarkPlugins` override, so we can:
//
//   1. Try with `remarkMdx` (rich MDX features, e.g. JSX-style components).
//   2. On failure, retry without `remarkMdx` (lenient HTML, like GitHub).
//   3. As a last resort, render the raw source in a paragraph so the user
//      never sees a crashed editor.
// ---------------------------------------------------------------------------

import { MarkdownPlugin, remarkMdx } from "@platejs/markdown";
import type { Descendant } from "platejs";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import type { PlateEditorInstance } from "@/components/editor/plate-editor";

const STRICT_PLUGINS = [remarkGfm, remarkMath, remarkMdx];
const LENIENT_PLUGINS = [remarkGfm, remarkMath];

function plainTextFallback(markdown: string): Descendant[] {
	return [
		{
			type: "p",
			children: [{ text: markdown }],
		} as unknown as Descendant,
	];
}

/**
 * Deserialize markdown into a Plate value, gracefully degrading when the
 * MDX-strict parser rejects raw HTML. Always returns a renderable value;
 * never throws.
 */
export function safeDeserializeMarkdown(
	editor: PlateEditorInstance,
	markdown: string
): Descendant[] {
	const api = editor.getApi(MarkdownPlugin).markdown;

	try {
		return api.deserialize(markdown, { remarkPlugins: STRICT_PLUGINS }) as Descendant[];
	} catch (mdxError) {
		if (process.env.NODE_ENV !== "production") {
			console.warn(
				"[plate-editor] MDX parse failed, retrying without remark-mdx:",
				mdxError
			);
		}
		try {
			return api.deserialize(markdown, { remarkPlugins: LENIENT_PLUGINS }) as Descendant[];
		} catch (fallbackError) {
			console.error("[plate-editor] markdown deserialize failed:", fallbackError);
			return plainTextFallback(markdown);
		}
	}
}
