import { Check, Copy } from "lucide-react";
import Image from "next/image";
import { useTheme } from "next-themes";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/cjs/styles/prism";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface MarkdownViewerProps {
	content: string;
	className?: string;
}

export function MarkdownViewer({ content, className }: MarkdownViewerProps) {
	const ref = useRef<HTMLDivElement>(null);
	// Memoize the markdown components to prevent unnecessary re-renders
	const components = useMemo(() => {
		return {
			// Define custom components for markdown elements
			p: ({ node, children, ...props }: any) => (
				<p className="my-2" {...props}>
					{children}
				</p>
			),
			a: ({ node, children, ...props }: any) => (
				<a className="text-primary hover:underline" {...props}>
					{children}
				</a>
			),
			li: ({ node, children, ...props }: any) => <li {...props}>{children}</li>,
			ul: ({ node, ...props }: any) => <ul className="list-disc pl-5 my-2" {...props} />,
			ol: ({ node, ...props }: any) => <ol className="list-decimal pl-5 my-2" {...props} />,
			h1: ({ node, children, ...props }: any) => (
				<h1 className="text-2xl font-bold mt-6 mb-2" {...props}>
					{children}
				</h1>
			),
			h2: ({ node, children, ...props }: any) => (
				<h2 className="text-xl font-bold mt-5 mb-2" {...props}>
					{children}
				</h2>
			),
			h3: ({ node, children, ...props }: any) => (
				<h3 className="text-lg font-bold mt-4 mb-2" {...props}>
					{children}
				</h3>
			),
			h4: ({ node, children, ...props }: any) => (
				<h4 className="text-base font-bold mt-3 mb-1" {...props}>
					{children}
				</h4>
			),
			blockquote: ({ node, ...props }: any) => (
				<blockquote className="border-l-4 border-muted pl-4 italic my-2" {...props} />
			),
			hr: ({ node, ...props }: any) => <hr className="my-4 border-muted" {...props} />,
			img: ({ node, ...props }: any) => (
				<Image
					className="max-w-full h-auto my-4 rounded"
					alt="markdown image"
					height={100}
					width={100}
					{...props}
				/>
			),
			table: ({ node, ...props }: any) => (
				<div className="overflow-x-auto my-4">
					<table className="min-w-full divide-y divide-border" {...props} />
				</div>
			),
			th: ({ node, ...props }: any) => (
				<th className="px-3 py-2 text-left font-medium bg-muted" {...props} />
			),
			td: ({ node, ...props }: any) => (
				<td className="px-3 py-2 border-t border-border" {...props} />
			),
			code: ({ node, className, children, ...props }: any) => {
				const match = /language-(\w+)/.exec(className || "");
				const language = match ? match[1] : "";
				const isInline = !match;

				if (isInline) {
					return (
						<code className="bg-muted px-1 py-0.5 rounded text-xs" {...props}>
							{children}
						</code>
					);
				}

				// For code blocks, add syntax highlighting and copy functionality
				return (
					<CodeBlock language={language} {...props}>
						{String(children).replace(/\n$/, "")}
					</CodeBlock>
				);
			},
		};
	}, []);

	return (
		<div className={cn("prose prose-sm dark:prose-invert max-w-none", className)} ref={ref}>
			<ReactMarkdown
				rehypePlugins={[rehypeRaw, rehypeSanitize]}
				remarkPlugins={[remarkGfm]}
				components={components}
			>
				{content}
			</ReactMarkdown>
		</div>
	);
}

// Code block component with syntax highlighting and copy functionality
const CodeBlock = ({ children, language }: { children: string; language: string }) => {
	const [copied, setCopied] = useState(false);
	const { resolvedTheme, theme } = useTheme();
	const [mounted, setMounted] = useState(false);

	// Prevent hydration issues
	useEffect(() => {
		setMounted(true);
	}, []);

	const handleCopy = async () => {
		await navigator.clipboard.writeText(children);
		setCopied(true);
		setTimeout(() => setCopied(false), 2000);
	};

	// Choose theme based on current system/user preference
	const isDarkTheme = mounted && (resolvedTheme === "dark" || theme === "dark");
	const syntaxTheme = isDarkTheme ? oneDark : oneLight;

	return (
		<div className="relative my-4 group">
			<div className="absolute right-2 top-2 z-10">
				<Button
					variant="ghost"
					onClick={handleCopy}
					className="p-1.5 rounded-md bg-background/80 hover:bg-background border border-border flex items-center justify-center transition-colors"
					aria-label="Copy code"
				>
					{copied ? (
						<Check size={14} className="text-green-500" />
					) : (
						<Copy size={14} className="text-muted-foreground" />
					)}
				</Button>
			</div>
			{mounted ? (
				<SyntaxHighlighter
					language={language || "text"}
					style={{
						...syntaxTheme,
						'pre[class*="language-"]': {
							...syntaxTheme['pre[class*="language-"]'],
							margin: 0,
							border: "none",
							borderRadius: "0.375rem",
							background: "var(--syntax-bg)",
						},
						'code[class*="language-"]': {
							...syntaxTheme['code[class*="language-"]'],
							border: "none",
							background: "var(--syntax-bg)",
						},
					}}
					customStyle={{
						margin: 0,
						borderRadius: "0.375rem",
						fontSize: "0.75rem",
						lineHeight: "1.5rem",
						backgroundColor: "var(--syntax-bg)",
						border: "none",
					}}
					codeTagProps={{
						className: "font-mono",
						style: {
							border: "none",
							background: "var(--syntax-bg)",
						},
					}}
					showLineNumbers={false}
					wrapLines={false}
					lineProps={{
						style: {
							wordBreak: "break-all",
							whiteSpace: "pre-wrap",
							border: "none",
							borderBottom: "none",
							paddingLeft: 0,
							paddingRight: 0,
							margin: "0.25rem 0",
						},
					}}
					PreTag="div"
				>
					{children}
				</SyntaxHighlighter>
			) : (
				<div className="bg-muted p-4 rounded-md">
					<pre className="m-0 p-0 border-0">
						<code className="text-xs font-mono border-0 leading-6">{children}</code>
					</pre>
				</div>
			)}
		</div>
	);
};
