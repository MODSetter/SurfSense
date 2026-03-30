"use client";

import "@assistant-ui/react-markdown/styles/dot.css";

import {
	MarkdownTextPrimitive,
	unstable_memoizeMarkdownComponents as memoizeMarkdownComponents,
	useIsMarkdownCodeBlock,
} from "@assistant-ui/react-markdown";
import { ExternalLinkIcon } from "lucide-react";
import dynamic from "next/dynamic";
import { useTheme } from "next-themes";
import { memo, type ReactNode } from "react";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { ImagePreview, ImageRoot, ImageZoom } from "@/components/assistant-ui/image";
import "katex/dist/katex.min.css";
import { InlineCitation, UrlCitation } from "@/components/assistant-ui/inline-citation";
import { Skeleton } from "@/components/ui/skeleton";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

function MarkdownCodeBlockSkeleton() {
	return (
		<div
			className="mt-4 overflow-hidden rounded-2xl border"
			style={{ background: "var(--syntax-bg)" }}
		>
			<div className="flex items-center justify-between gap-4 border-b px-4 py-2">
				<Skeleton className="h-3 w-16" />
				<Skeleton className="h-8 w-8 rounded-md" />
			</div>
			<div className="space-y-2 p-4">
				<Skeleton className="h-4 w-11/12" />
				<Skeleton className="h-4 w-10/12" />
				<Skeleton className="h-4 w-8/12" />
				<Skeleton className="h-4 w-9/12" />
			</div>
		</div>
	);
}

const LazyMarkdownCodeBlock = dynamic(
	() => import("./markdown-code-block").then((mod) => mod.MarkdownCodeBlock),
	{
		loading: () => <MarkdownCodeBlockSkeleton />,
	}
);

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

/**
 * Helper to process children and replace citation patterns with components
 */
function processChildrenWithCitations(children: ReactNode): ReactNode {
	if (typeof children === "string") {
		const parsed = parseTextWithCitations(children);
		return parsed.length === 1 && typeof parsed[0] === "string" ? children : parsed;
	}

	if (Array.isArray(children)) {
		return children.map((child) => {
			if (typeof child === "string") {
				const parsed = parseTextWithCitations(child);
				return parsed.length === 1 && typeof parsed[0] === "string" ? (
					child
				) : (
					<span key={child}>{parsed}</span>
				);
			}
			return child;
		});
	}

	return children;
}

function extractDomain(url: string): string {
	try {
		const parsed = new URL(url);
		return parsed.hostname.replace(/^www\./, "");
	} catch {
		return "";
	}
}

function MarkdownImage({ src, alt }: { src?: string; alt?: string }) {
	if (!src) return null;

	const domain = extractDomain(src);

	return (
		<div className="my-4 w-fit max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<ImageRoot variant="ghost" size="full">
				<ImageZoom src={src} alt={alt || "Image"}>
					<ImagePreview
						src={src}
						alt={alt || "Image"}
						className="max-h-[20rem] w-auto max-w-full object-contain"
					/>
				</ImageZoom>
			</ImageRoot>

			<div className="flex items-center justify-between px-5 py-3">
				<div className="min-w-0 flex-1">
					{alt && alt !== "Image" && (
						<p className="text-sm font-semibold text-foreground line-clamp-2">{alt}</p>
					)}
					{domain && <p className="text-xs text-muted-foreground mt-0.5 truncate">{domain}</p>}
				</div>
				<a
					href={src}
					target="_blank"
					rel="noopener noreferrer"
					className="ml-3 shrink-0 inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-muted"
					onClick={(e) => e.stopPropagation()}
				>
					Open
					<ExternalLinkIcon className="size-3" />
				</a>
			</div>
		</div>
	);
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
		<div className="aui-md-table-wrapper my-5 overflow-hidden rounded-2xl border">
			<Table className={cn("aui-md-table", className)} {...props} />
		</div>
	),
	thead: ({ className, ...props }) => (
		<TableHeader className={cn("aui-md-thead", className)} {...props} />
	),
	tbody: ({ className, ...props }) => (
		<TableBody className={cn("aui-md-tbody", className)} {...props} />
	),
	th: ({ className, children, ...props }) => (
		<TableHead
			className={cn(
				"aui-md-th bg-muted/50 whitespace-normal [[align=center]]:text-center [[align=right]]:text-right",
				className
			)}
			{...props}
		>
			{processChildrenWithCitations(children)}
		</TableHead>
	),
	td: ({ className, children, ...props }) => (
		<TableCell
			className={cn(
				"aui-md-td whitespace-normal [[align=center]]:text-center [[align=right]]:text-right",
				className
			)}
			{...props}
		>
			{processChildrenWithCitations(children)}
		</TableCell>
	),
	tr: ({ className, ...props }) => <TableRow className={cn("aui-md-tr", className)} {...props} />,
	sup: ({ className, ...props }) => (
		<sup className={cn("aui-md-sup [&>a]:text-xs [&>a]:no-underline", className)} {...props} />
	),
	pre: ({ children }) => <>{children}</>,
	code: function Code({ className, children, ...props }) {
		const isCodeBlock = useIsMarkdownCodeBlock();
		const { resolvedTheme } = useTheme();
		if (!isCodeBlock) {
			return (
				<code
					className={cn(
						"aui-md-inline-code rounded-md border bg-muted px-1.5 py-0.5 font-mono text-[0.9em] font-normal",
						className
					)}
					{...props}
				>
					{children}
				</code>
			);
		}
		const language = /language-(\w+)/.exec(className || "")?.[1] ?? "text";
		const codeString = String(children).replace(/\n$/, "");
		return (
			<LazyMarkdownCodeBlock
				className={className}
				language={language}
				codeText={codeString}
				isDarkMode={resolvedTheme === "dark"}
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
	img: ({ src, alt }) => (
		<MarkdownImage src={typeof src === "string" ? src : undefined} alt={alt} />
	),
	CodeHeader: () => null,
});
