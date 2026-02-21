"use client";

import "@assistant-ui/react-markdown/styles/dot.css";

import {
	type CodeHeaderProps,
	MarkdownTextPrimitive,
	unstable_memoizeMarkdownComponents as memoizeMarkdownComponents,
	useIsMarkdownCodeBlock,
} from "@assistant-ui/react-markdown";
import { CheckIcon, CopyIcon } from "lucide-react";
import { type FC, memo, type ReactNode, useState } from "react";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";
import { InlineCitation, UrlCitation } from "@/components/assistant-ui/inline-citation";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { cn } from "@/lib/utils";

// Storage for URL citations replaced during preprocess to avoid GFM autolink interference.
// Populated in preprocessMarkdown, consumed in parseTextWithCitations.
let _pendingUrlCitations = new Map<string, string>();
let _urlCiteIdx = 0;

/**
 * Preprocess raw markdown before it reaches the remark/rehype pipeline.
 * - Replaces URL-based citations with safe placeholders (prevents GFM autolinks)
 * - Normalises LaTeX delimiters to dollar-sign syntax for remark-math
 */
function preprocessMarkdown(content: string): string {
	// Replace URL-based citations with safe placeholders BEFORE markdown parsing.
	// GFM autolinks would otherwise convert the https://... inside [citation:URL]
	// into an <a> element, splitting the text and preventing our citation regex
	// from matching the full pattern.
	_pendingUrlCitations = new Map();
	_urlCiteIdx = 0;
	content = content.replace(
		/[[【]\u200B?citation:\s*(https?:\/\/[^\]】\u200B]+)\s*\u200B?[\]】]/g,
		(_, url) => {
			const key = `urlcite${_urlCiteIdx++}`;
			_pendingUrlCitations.set(key, url.trim());
			return `[citation:${key}]`;
		}
	);

	// 1. Block math: \[...\] → $$...$$
	content = content.replace(/\\\[([\s\S]*?)\\\]/g, (_, inner) => `$$${inner}$$`);
	// 2. Inline math: \(...\) → $...$
	content = content.replace(/\\\(([\s\S]*?)\\\)/g, (_, inner) => `$${inner}$`);
	// 3. Block: \begin{equation}...\end{equation} → $$...$$
	content = content.replace(
		/\\begin\{equation\}([\s\S]*?)\\end\{equation\}/g,
		(_, inner) => `$$${inner}$$`
	);
	// 4. Block: \begin{displaymath}...\end{displaymath} → $$...$$
	content = content.replace(
		/\\begin\{displaymath\}([\s\S]*?)\\end\{displaymath\}/g,
		(_, inner) => `$$${inner}$$`
	);
	// 5. Inline: \begin{math}...\end{math} → $...$
	content = content.replace(/\\begin\{math\}([\s\S]*?)\\end\{math\}/g, (_, inner) => `$${inner}$`);
	// 6. Strip backtick wrapping around math: `$$...$$` → $$...$$ and `$...$` → $...$
	content = content.replace(/`(\${1,2})((?:(?!\1).)+)\1`/g, "$1$2$1");

	// Ensure markdown headings (## ...) always start on their own line.
	content = content.replace(/([^\n])(#{1,6}\s)/g, "$1\n\n$2");

	return content;
}

// Matches [citation:...] with numeric IDs (incl. doc- prefix, comma-separated),
// URL-based IDs from live web search, or urlciteN placeholders from preprocess.
// Also matches Chinese brackets 【】 and handles zero-width spaces that LLM sometimes inserts.
const CITATION_REGEX =
	/[[【]\u200B?citation:\s*(https?:\/\/[^\]】\u200B]+|urlcite\d+|(?:doc-)?\d+(?:\s*,\s*(?:doc-)?\d+)*)\s*\u200B?[\]】]/g;

/**
 * Parses text and replaces [citation:XXX] patterns with citation components.
 * Supports:
 *  - Numeric chunk IDs: [citation:123]
 *  - Doc-prefixed IDs: [citation:doc-123]
 *  - Comma-separated IDs: [citation:4149, 4150, 4151]
 *  - URL-based citations from live search: [citation:https://example.com/page]
 */
function parseTextWithCitations(text: string): ReactNode[] {
	const parts: ReactNode[] = [];
	let lastIndex = 0;
	let match: RegExpExecArray | null;
	let instanceIndex = 0;

	CITATION_REGEX.lastIndex = 0;

	match = CITATION_REGEX.exec(text);
	while (match !== null) {
		if (match.index > lastIndex) {
			parts.push(text.substring(lastIndex, match.index));
		}

		const captured = match[1];

		if (captured.startsWith("http://") || captured.startsWith("https://")) {
			parts.push(<UrlCitation key={`citation-url-${instanceIndex}`} url={captured.trim()} />);
			instanceIndex++;
		} else if (captured.startsWith("urlcite")) {
			const url = _pendingUrlCitations.get(captured);
			if (url) {
				parts.push(<UrlCitation key={`citation-url-${instanceIndex}`} url={url} />);
			}
			instanceIndex++;
		} else {
			const rawIds = captured.split(",").map((s) => s.trim());
			for (const rawId of rawIds) {
				const isDocsChunk = rawId.startsWith("doc-");
				const chunkId = Number.parseInt(isDocsChunk ? rawId.slice(4) : rawId, 10);
				parts.push(
					<InlineCitation
						key={`citation-${isDocsChunk ? "doc-" : ""}${chunkId}-${instanceIndex}`}
						chunkId={chunkId}
						isDocsChunk={isDocsChunk}
					/>
				);
				instanceIndex++;
			}
		}

		lastIndex = match.index + match[0].length;
		match = CITATION_REGEX.exec(text);
	}

	if (lastIndex < text.length) {
		parts.push(text.substring(lastIndex));
	}

	return parts.length > 0 ? parts : [text];
}

const MarkdownTextImpl = () => {
	return (
		<MarkdownTextPrimitive
			remarkPlugins={[remarkGfm, remarkMath]}
			rehypePlugins={[rehypeKatex]}
			className="aui-md"
			components={defaultComponents}
			preprocess={preprocessMarkdown}
		/>
	);
};

export const MarkdownText = memo(MarkdownTextImpl);

const CodeHeader: FC<CodeHeaderProps> = ({ language, code }) => {
	const { isCopied, copyToClipboard } = useCopyToClipboard();
	const onCopy = () => {
		if (!code || isCopied) return;
		copyToClipboard(code);
	};

	return (
		<div className="aui-code-header-root mt-4 flex items-center justify-between gap-4 rounded-t-lg bg-muted-foreground/15 px-4 py-2 font-semibold text-foreground text-sm dark:bg-muted-foreground/20">
			<span className="aui-code-header-language lowercase [&>span]:text-xs">{language}</span>
			<TooltipIconButton tooltip="Copy" onClick={onCopy}>
				{!isCopied && <CopyIcon />}
				{isCopied && <CheckIcon />}
			</TooltipIconButton>
		</div>
	);
};

const useCopyToClipboard = ({ copiedDuration = 3000 }: { copiedDuration?: number } = {}) => {
	const [isCopied, setIsCopied] = useState<boolean>(false);

	const copyToClipboard = (value: string) => {
		if (!value) return;

		navigator.clipboard.writeText(value).then(() => {
			setIsCopied(true);
			setTimeout(() => setIsCopied(false), copiedDuration);
		});
	};

	return { isCopied, copyToClipboard };
};

/**
 * Helper to process children and replace citation patterns with components
 */
function processChildrenWithCitations(children: ReactNode): ReactNode {
	if (typeof children === "string") {
		const parsed = parseTextWithCitations(children);
		return parsed.length === 1 && typeof parsed[0] === "string" ? children : <>{parsed}</>;
	}

	if (Array.isArray(children)) {
		return children.map((child, index) => {
			if (typeof child === "string") {
				const parsed = parseTextWithCitations(child);
				return parsed.length === 1 && typeof parsed[0] === "string" ? (
					child
				) : (
					<span key={index}>{parsed}</span>
				);
			}
			return child;
		});
	}

	return children;
}

const defaultComponents = memoizeMarkdownComponents({
	h1: ({ className, children, ...props }) => (
		<h1
			className={cn(
				"aui-md-h1 mb-8 scroll-m-20 font-extrabold text-4xl tracking-tight last:mb-0",
				className
			)}
			{...props}
		>
			{processChildrenWithCitations(children)}
		</h1>
	),
	h2: ({ className, children, ...props }) => (
		<h2
			className={cn(
				"aui-md-h2 mt-8 mb-4 scroll-m-20 font-semibold text-3xl tracking-tight first:mt-0 last:mb-0",
				className
			)}
			{...props}
		>
			{processChildrenWithCitations(children)}
		</h2>
	),
	h3: ({ className, children, ...props }) => (
		<h3
			className={cn(
				"aui-md-h3 mt-6 mb-4 scroll-m-20 font-semibold text-2xl tracking-tight first:mt-0 last:mb-0",
				className
			)}
			{...props}
		>
			{processChildrenWithCitations(children)}
		</h3>
	),
	h4: ({ className, children, ...props }) => (
		<h4
			className={cn(
				"aui-md-h4 mt-6 mb-4 scroll-m-20 font-semibold text-xl tracking-tight first:mt-0 last:mb-0",
				className
			)}
			{...props}
		>
			{processChildrenWithCitations(children)}
		</h4>
	),
	h5: ({ className, children, ...props }) => (
		<h5
			className={cn("aui-md-h5 my-4 font-semibold text-lg first:mt-0 last:mb-0", className)}
			{...props}
		>
			{processChildrenWithCitations(children)}
		</h5>
	),
	h6: ({ className, children, ...props }) => (
		<h6 className={cn("aui-md-h6 my-4 font-semibold first:mt-0 last:mb-0", className)} {...props}>
			{processChildrenWithCitations(children)}
		</h6>
	),
	p: ({ className, children, ...props }) => (
		<p className={cn("aui-md-p mt-5 mb-5 leading-7 first:mt-0 last:mb-0", className)} {...props}>
			{processChildrenWithCitations(children)}
		</p>
	),
	a: ({ className, children, ...props }) => (
		<a
			className={cn("aui-md-a font-medium text-primary underline underline-offset-4", className)}
			{...props}
		>
			{processChildrenWithCitations(children)}
		</a>
	),
	blockquote: ({ className, children, ...props }) => (
		<blockquote className={cn("aui-md-blockquote border-l-2 pl-6 italic", className)} {...props}>
			{processChildrenWithCitations(children)}
		</blockquote>
	),
	ul: ({ className, ...props }) => (
		<ul className={cn("aui-md-ul my-5 ml-6 list-disc [&>li]:mt-2", className)} {...props} />
	),
	ol: ({ className, ...props }) => (
		<ol className={cn("aui-md-ol my-5 ml-6 list-decimal [&>li]:mt-2", className)} {...props} />
	),
	li: ({ className, children, ...props }) => (
		<li className={cn("aui-md-li", className)} {...props}>
			{processChildrenWithCitations(children)}
		</li>
	),
	hr: ({ className, ...props }) => (
		<hr className={cn("aui-md-hr my-5 border-b", className)} {...props} />
	),
	table: ({ className, ...props }) => (
		<div className="aui-md-table-wrapper my-5 w-full overflow-x-auto">
			<table
				className={cn("aui-md-table w-full min-w-max border-separate border-spacing-0", className)}
				{...props}
			/>
		</div>
	),
	th: ({ className, children, ...props }) => (
		<th
			className={cn(
				"aui-md-th bg-muted px-4 py-2 text-left font-bold first:rounded-tl-lg last:rounded-tr-lg [[align=center]]:text-center [[align=right]]:text-right",
				className
			)}
			{...props}
		>
			{processChildrenWithCitations(children)}
		</th>
	),
	td: ({ className, children, ...props }) => (
		<td
			className={cn(
				"aui-md-td border-b border-l px-4 py-2 text-left last:border-r [[align=center]]:text-center [[align=right]]:text-right",
				className
			)}
			{...props}
		>
			{processChildrenWithCitations(children)}
		</td>
	),
	tr: ({ className, ...props }) => (
		<tr
			className={cn(
				"aui-md-tr m-0 border-b p-0 first:border-t [&:last-child>td:first-child]:rounded-bl-lg [&:last-child>td:last-child]:rounded-br-lg",
				className
			)}
			{...props}
		/>
	),
	sup: ({ className, ...props }) => (
		<sup className={cn("aui-md-sup [&>a]:text-xs [&>a]:no-underline", className)} {...props} />
	),
	pre: ({ className, ...props }) => (
		<pre
			className={cn(
				"aui-md-pre overflow-x-auto rounded-t-none! rounded-b-lg bg-black p-4 text-white",
				className
			)}
			{...props}
		/>
	),
	code: function Code({ className, ...props }) {
		const isCodeBlock = useIsMarkdownCodeBlock();
		return (
			<code
				className={cn(
					!isCodeBlock && "aui-md-inline-code rounded border bg-muted font-semibold",
					className
				)}
				{...props}
			/>
		);
	},
	strong: ({ className, children, ...props }) => (
		<strong className={cn("aui-md-strong font-semibold", className)} {...props}>
			{processChildrenWithCitations(children)}
		</strong>
	),
	em: ({ className, children, ...props }) => (
		<em className={cn("aui-md-em", className)} {...props}>
			{processChildrenWithCitations(children)}
		</em>
	),
	CodeHeader,
});
