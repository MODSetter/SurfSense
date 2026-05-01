import { createCodePlugin } from "@streamdown/code";
import { createMathPlugin } from "@streamdown/math";
import { Streamdown, type StreamdownProps } from "streamdown";
import "katex/dist/katex.min.css";
import Image from "next/image";
import { useMemo } from "react";
import { processChildrenWithCitations } from "@/components/citations/citation-renderer";
import {
	type CitationUrlMap,
	preprocessCitationMarkdown,
} from "@/lib/citations/citation-parser";
import { cn } from "@/lib/utils";

const code = createCodePlugin({
	themes: ["nord", "nord"],
});

const math = createMathPlugin({
	// Disabled so currency like "$3,120.00 and ... $0.00" isn't parsed as
	// inline LaTeX. convertLatexDelimiters() below normalises any genuine
	// inline math (\(...\), $...$ starting with a LaTeX command, etc.) to
	// $$...$$, so this flip doesn't lose any math rendering.
	singleDollarTextMath: false,
});

interface MarkdownViewerProps {
	content: string;
	className?: string;
	maxLength?: number;
	/**
	 * When true, render `[citation:N]` / `[citation:URL]` tokens as the
	 * interactive citation badges/popovers used in chat. Default `false`
	 * so callers that don't need citations are unchanged.
	 *
	 * Note: we deliberately do NOT override `<a>` to inject citations into
	 * link text — that would produce `<button>` inside `<a>` (invalid
	 * HTML). A `[citation:N]` token literally placed inside markdown link
	 * text stays as raw text.
	 */
	enableCitations?: boolean;
}

const EMPTY_URL_MAP: CitationUrlMap = new Map();

/**
 * If the entire content is wrapped in a single ```markdown or ```md
 * code fence, strip the fence so the inner markdown renders properly.
 */
function stripOuterMarkdownFence(content: string): string {
	const trimmed = content.trim();
	// Match 3+ backtick fences (LLMs escalate to 4+ when content has triple-backtick blocks)
	const match = trimmed.match(/^(`{3,})(?:markdown|md)?\s*\n([\s\S]+?)\n\1\s*$/);
	return match ? match[2] : content;
}

/**
 * Convert all LaTeX delimiter styles to the double-dollar syntax
 * that Streamdown's @streamdown/math plugin understands.
 *
 * Streamdown math conventions (different from remark-math!):
 *   $$...$$  on the SAME line     → inline math
 *   $$\n...\n$$  on SEPARATE lines → block (display) math
 *
 * Conversions performed:
 *   \[...\]                              → $$\n ... \n$$  (block math)
 *   \(...\)                              → $$...$$        (inline math, same line)
 *   \begin{equation}...\end{equation}    → $$\n ... \n$$  (block math)
 *   \begin{displaymath}...\end{displaymath} → $$\n ... \n$$ (block math)
 *   \begin{math}...\end{math}            → $$...$$        (inline math, same line)
 *   `$$ … $$`                             → $$ … $$       (strip wrapping backtick code)
 *   `$ … $`                               → $ … $         (strip wrapping backtick code)
 *   $...$                                 → $$...$$        (normalise single-$ to double-$$)
 */
function convertLatexDelimiters(content: string): string {
	// 1. Block math: \[...\] → $$\n...\n$$ (display math on separate lines)
	content = content.replace(/\\\[([\s\S]*?)\\\]/g, (_, inner) => `\n$$\n${inner.trim()}\n$$\n`);
	// 2. Inline math: \(...\) → $$...$$ (inline math on same line)
	content = content.replace(/\\\(([\s\S]*?)\\\)/g, (_, inner) => `$$${inner.trim()}$$`);
	// 3. Block: \begin{equation}...\end{equation} → $$\n...\n$$
	content = content.replace(
		/\\begin\{equation\}([\s\S]*?)\\end\{equation\}/g,
		(_, inner) => `\n$$\n${inner.trim()}\n$$\n`
	);
	// 4. Block: \begin{displaymath}...\end{displaymath} → $$\n...\n$$
	content = content.replace(
		/\\begin\{displaymath\}([\s\S]*?)\\end\{displaymath\}/g,
		(_, inner) => `\n$$\n${inner.trim()}\n$$\n`
	);
	// 5. Inline: \begin{math}...\end{math} → $$...$$
	content = content.replace(
		/\\begin\{math\}([\s\S]*?)\\end\{math\}/g,
		(_, inner) => `$$${inner.trim()}$$`
	);
	// 6. Strip backtick wrapping around math: `$$...$$` → $$...$$ and `$...$` → $...$
	content = content.replace(/`(\${1,2})((?:(?!\1).)+)\1`/g, "$1$2$1");
	// 7. Normalise single-dollar $...$ to double-dollar $$...$$ so they render
	//    reliably in Streamdown (single-$ has strict no-space rules that often fail).
	//    We match $…$ where the content starts with a backslash (LaTeX command)
	//    to avoid converting currency like $50.
	content = content.replace(
		/(?<!\$)\$(?!\$)(\\[a-zA-Z][\s\S]*?)(?<!\$)\$(?!\$)/g,
		(_, inner) => `$$${inner.trim()}$$`
	);
	return content;
}

export function MarkdownViewer({
	content,
	className,
	maxLength,
	enableCitations = false,
}: MarkdownViewerProps) {
	const isTruncated = maxLength != null && content.length > maxLength;
	const displayContent = isTruncated ? content.slice(0, maxLength) : content;

	// Preprocess for URL placeholders BEFORE LaTeX so GFM autolinks don't
	// split `[citation:https://…]` apart. The preprocess is code-fence
	// aware so citations inside fenced code stay literal.
	const { processedContent, urlMap } = useMemo(() => {
		const stripped = stripOuterMarkdownFence(displayContent);
		if (!enableCitations) {
			return {
				processedContent: convertLatexDelimiters(stripped),
				urlMap: EMPTY_URL_MAP,
			};
		}
		const { content: rewritten, urlMap: map } = preprocessCitationMarkdown(stripped);
		return {
			processedContent: convertLatexDelimiters(rewritten),
			urlMap: map,
		};
	}, [displayContent, enableCitations]);

	// Phrasing/block renderers wrap their string children through the
	// citation renderer when `enableCitations` is on. We deliberately do
	// NOT override `<a>` (would produce <button> inside <a>) and we do
	// NOT touch the inline/fenced `code` paths (citations stay literal
	// inside code, matching markdown-text.tsx behavior).
	const wrap = (children: React.ReactNode): React.ReactNode =>
		enableCitations ? processChildrenWithCitations(children, urlMap) : children;

	const components: StreamdownProps["components"] = {
		p: ({ children, ...props }) => (
			<p className="my-2" {...props}>
				{wrap(children)}
			</p>
		),
		a: ({ children, ...props }) => (
			<a
				className="text-primary hover:underline"
				target="_blank"
				rel="noopener noreferrer"
				{...props}
			>
				{children}
			</a>
		),
		li: ({ children, ...props }) => <li {...props}>{wrap(children)}</li>,
		ul: ({ ...props }) => <ul className="list-disc pl-5 my-2" {...props} />,
		ol: ({ ...props }) => <ol className="list-decimal pl-5 my-2" {...props} />,
		h1: ({ children, ...props }) => (
			<h1 className="text-2xl font-bold mt-6 mb-2" {...props}>
				{wrap(children)}
			</h1>
		),
		h2: ({ children, ...props }) => (
			<h2 className="text-xl font-bold mt-5 mb-2" {...props}>
				{wrap(children)}
			</h2>
		),
		h3: ({ children, ...props }) => (
			<h3 className="text-lg font-bold mt-4 mb-2" {...props}>
				{wrap(children)}
			</h3>
		),
		h4: ({ children, ...props }) => (
			<h4 className="text-base font-bold mt-3 mb-1" {...props}>
				{wrap(children)}
			</h4>
		),
		h5: ({ children, ...props }) => (
			<h5 className="text-sm font-bold mt-3 mb-1" {...props}>
				{wrap(children)}
			</h5>
		),
		h6: ({ children, ...props }) => (
			<h6 className="text-xs font-bold mt-3 mb-1" {...props}>
				{wrap(children)}
			</h6>
		),
		strong: ({ children, ...props }) => (
			<strong className="font-semibold" {...props}>
				{wrap(children)}
			</strong>
		),
		em: ({ children, ...props }) => <em {...props}>{wrap(children)}</em>,
		blockquote: ({ children, ...props }) => (
			<blockquote className="border-l-4 border-muted pl-4 italic my-2" {...props}>
				{wrap(children)}
			</blockquote>
		),
		hr: ({ ...props }) => <hr className="my-4 border-muted" {...props} />,
		img: ({ src, alt, width: _w, height: _h, ...props }) => {
			const isDataOrUnknownUrl =
				typeof src === "string" && (src.startsWith("data:") || !src.startsWith("http"));

			return isDataOrUnknownUrl ? (
				// eslint-disable-next-line @next/next/no-img-element
				<img
					className="max-w-full h-auto my-4 rounded"
					alt={alt || "markdown image"}
					src={src}
					loading="lazy"
					{...props}
				/>
			) : (
				<Image
					className="max-w-full h-auto my-4 rounded"
					alt={alt || "markdown image"}
					src={typeof src === "string" ? src : ""}
					width={_w || 800}
					height={_h || 600}
					sizes="(max-width: 768px) 100vw, (max-width: 1200px) 75vw, 60vw"
					unoptimized={isDataOrUnknownUrl}
					{...props}
				/>
			);
		},
		table: ({ ...props }) => (
			<div className="overflow-x-auto my-4 rounded-lg border border-border w-full">
				<table className="w-full divide-y divide-border" {...props} />
			</div>
		),
		th: ({ children, ...props }) => (
			<th
				className="px-4 py-2.5 text-left text-sm font-semibold text-muted-foreground/80 bg-muted/30 border-r border-border/40 last:border-r-0"
				{...props}
			>
				{wrap(children)}
			</th>
		),
		td: ({ children, ...props }) => (
			<td
				className="px-4 py-2.5 text-sm border-t border-r border-border/40 last:border-r-0"
				{...props}
			>
				{wrap(children)}
			</td>
		),
	};

	return (
		<div
			className={cn(
				"max-w-none overflow-hidden",
				"[&_[data-streamdown=code-block-header]]:!bg-transparent",
				"[&_[data-streamdown=code-block]>*]:!border-none [&_[data-streamdown=code-block]>*]:![box-shadow:none]",
				"[&_[data-streamdown=code-block-download-button]]:!hidden",
				className
			)}
		>
			<Streamdown
				components={components}
				plugins={{ code, math }}
				controls={{ code: true }}
				mode="static"
			>
				{processedContent}
			</Streamdown>
			{isTruncated && (
				<p className="mt-4 text-sm text-muted-foreground italic">
					Content truncated ({Math.round(content.length / 1024)}KB total). Showing first{" "}
					{Math.round(maxLength / 1024)}KB.
				</p>
			)}
		</div>
	);
}
