import Image from "next/image";
import { Streamdown, type StreamdownProps } from "streamdown";
import { createCodePlugin } from "@streamdown/code";
import { createMathPlugin } from "@streamdown/math";
import "katex/dist/katex.min.css";
import { cn } from "@/lib/utils";

const code = createCodePlugin({
	themes: ["nord", "nord"],
});

const math = createMathPlugin({
	singleDollarTextMath: true,
});

interface MarkdownViewerProps {
	content: string;
	className?: string;
}

/**
 * If the entire content is wrapped in a single ```markdown or ```md
 * code fence, strip the fence so the inner markdown renders properly.
 */
function stripOuterMarkdownFence(content: string): string {
	const trimmed = content.trim();
	const match = trimmed.match(/^```(?:markdown|md)?\s*\n([\s\S]+?)\n```\s*$/);
	return match ? match[1] : content;
}

/**
 * Convert all LaTeX delimiter styles to the dollar-sign syntax
 * that remark-math understands, and normalise edge-cases that
 * commonly appear in LLM-generated markdown.
 *
 *   \[...\]                              → $$ ... $$  (block / display math)
 *   \(...\)                              → $ ... $    (inline math)
 *   \begin{equation}...\end{equation}    → $$ ... $$  (block math)
 *   \begin{displaymath}...\end{displaymath} → $$ ... $$ (block math)
 *   \begin{math}...\end{math}            → $ ... $    (inline math)
 *   same-line $$…$$                       → $ ... $    (inline math — display math
 *                                                        can't live inside table cells)
 *   `$$ … $$`                             → $$ … $$    (strip wrapping backtick code)
 *   `$ … $`                               → $ … $      (strip wrapping backtick code)
 */
function convertLatexDelimiters(content: string): string {
	// 1. Block math: \[...\] → $$...$$
	content = content.replace(/\\\[([\s\S]*?)\\\]/g, (_, inner) => `$$${inner}$$`);
	// 2. Inline math: \(...\) → $...$
	content = content.replace(/\\\(([\s\S]*?)\\\)/g, (_, inner) => `$${inner}$`);
	// 3. Block: \begin{equation}...\end{equation} → $$...$$
	content = content.replace(
		/\\begin\{equation\}([\s\S]*?)\\end\{equation\}/g,
		(_, inner) => `$$${inner}$$`,
	);
	// 4. Block: \begin{displaymath}...\end{displaymath} → $$...$$
	content = content.replace(
		/\\begin\{displaymath\}([\s\S]*?)\\end\{displaymath\}/g,
		(_, inner) => `$$${inner}$$`,
	);
	// 5. Inline: \begin{math}...\end{math} → $...$
	content = content.replace(
		/\\begin\{math\}([\s\S]*?)\\end\{math\}/g,
		(_, inner) => `$${inner}$`,
	);
	// 6. Strip backtick wrapping around math: `$$...$$` → $$...$$ and `$...$` → $...$
	content = content.replace(/`(\${1,2})((?:(?!\1).)+)\1`/g, "$1$2$1");
	// 7. Same-line $$...$$ → $...$ (inline math) so it works inside table cells.
	//    True display math has $$ on its own line, so this only affects inline usage.
	content = content.replace(/\$\$([^\n]+?)\$\$/g, (_, inner) => `$${inner}$`);
	return content;
}

export function MarkdownViewer({ content, className }: MarkdownViewerProps) {
	const processedContent = convertLatexDelimiters(stripOuterMarkdownFence(content));
	const components: StreamdownProps["components"] = {
		p: ({ children, ...props }) => (
			<p className="my-2" {...props}>
				{children}
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
		li: ({ children, ...props }) => <li {...props}>{children}</li>,
		ul: ({ ...props }) => <ul className="list-disc pl-5 my-2" {...props} />,
		ol: ({ ...props }) => <ol className="list-decimal pl-5 my-2" {...props} />,
		h1: ({ children, ...props }) => (
			<h1 className="text-2xl font-bold mt-6 mb-2" {...props}>
				{children}
			</h1>
		),
		h2: ({ children, ...props }) => (
			<h2 className="text-xl font-bold mt-5 mb-2" {...props}>
				{children}
			</h2>
		),
		h3: ({ children, ...props }) => (
			<h3 className="text-lg font-bold mt-4 mb-2" {...props}>
				{children}
			</h3>
		),
		h4: ({ children, ...props }) => (
			<h4 className="text-base font-bold mt-3 mb-1" {...props}>
				{children}
			</h4>
		),
		blockquote: ({ ...props }) => (
			<blockquote className="border-l-4 border-muted pl-4 italic my-2" {...props} />
		),
		hr: ({ ...props }) => <hr className="my-4 border-muted" {...props} />,
		img: ({ src, alt, width: _w, height: _h, ...props }) => (
			<Image
				className="max-w-full h-auto my-4 rounded"
				alt={alt || "markdown image"}
				height={100}
				width={100}
				src={typeof src === "string" ? src : ""}
				{...props}
			/>
		),
		table: ({ ...props }) => (
			<div className="overflow-x-auto my-4 rounded-lg border border-border w-full">
				<table className="w-full divide-y divide-border" {...props} />
			</div>
		),
		th: ({ ...props }) => (
			<th
				className="px-4 py-2.5 text-left text-sm font-semibold text-muted-foreground/80 bg-muted/30 border-r border-border/40 last:border-r-0"
				{...props}
			/>
		),
		td: ({ ...props }) => (
			<td
				className="px-4 py-2.5 text-sm border-t border-r border-border/40 last:border-r-0"
				{...props}
			/>
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
		</div>
	);
}
