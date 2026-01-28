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
import remarkGfm from "remark-gfm";
import { InlineCitation } from "@/components/assistant-ui/inline-citation";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { cn } from "@/lib/utils";

// Citation pattern: [citation:CHUNK_ID] or [citation:doc-CHUNK_ID]
// Also matches Chinese brackets 【】 and handles zero-width spaces that LLM sometimes inserts
const CITATION_REGEX = /[[【]\u200B?citation:(doc-)?(\d+)\u200B?[\]】]/g;

// Track chunk IDs to citation numbers mapping for consistent numbering
// This map is reset when a new message starts rendering
// Uses string keys to differentiate between doc and regular chunks (e.g., "doc-123" vs "123")
let chunkIdToCitationNumber: Map<string, number> = new Map();
let nextCitationNumber = 1;

/**
 * Resets the citation counter - should be called at the start of each message
 */
export function resetCitationCounter() {
	chunkIdToCitationNumber = new Map();
	nextCitationNumber = 1;
}

/**
 * Gets or assigns a citation number for a chunk ID
 * Uses string key to differentiate between doc and regular chunks
 */
function getCitationNumber(chunkId: number, isDocsChunk: boolean): number {
	const key = isDocsChunk ? `doc-${chunkId}` : String(chunkId);
	const existingNumber = chunkIdToCitationNumber.get(key);
	if (existingNumber === undefined) {
		chunkIdToCitationNumber.set(key, nextCitationNumber++);
	}
	return chunkIdToCitationNumber.get(key)!;
}

/**
 * Parses text and replaces [citation:XXX] patterns with InlineCitation components
 * Supports both regular chunks [citation:123] and docs chunks [citation:doc-123]
 */
function parseTextWithCitations(text: string): ReactNode[] {
	const parts: ReactNode[] = [];
	let lastIndex = 0;
	let match: RegExpExecArray | null;
	let instanceIndex = 0;

	// Reset regex state
	CITATION_REGEX.lastIndex = 0;

	while ((match = CITATION_REGEX.exec(text)) !== null) {
		// Add text before the citation
		if (match.index > lastIndex) {
			parts.push(text.substring(lastIndex, match.index));
		}

		// Check if this is a docs chunk (has "doc-" prefix)
		const isDocsChunk = match[1] === "doc-";
		const chunkId = Number.parseInt(match[2], 10);
		const citationNumber = getCitationNumber(chunkId, isDocsChunk);
		parts.push(
			<InlineCitation
				key={`citation-${isDocsChunk ? "doc-" : ""}${chunkId}-${instanceIndex}`}
				chunkId={chunkId}
				citationNumber={citationNumber}
				isDocsChunk={isDocsChunk}
			/>
		);

		lastIndex = match.index + match[0].length;
		instanceIndex++;
	}

	// Add any remaining text after the last citation
	if (lastIndex < text.length) {
		parts.push(text.substring(lastIndex));
	}

	return parts.length > 0 ? parts : [text];
}

const MarkdownTextImpl = () => {
	return (
		<MarkdownTextPrimitive
			remarkPlugins={[remarkGfm]}
			className="aui-md"
			components={defaultComponents}
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
