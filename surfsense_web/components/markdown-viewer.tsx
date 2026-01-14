import Image from "next/image";
import { Streamdown, type StreamdownProps } from "streamdown";
import { cn } from "@/lib/utils";

interface MarkdownViewerProps {
	content: string;
	className?: string;
}

export function MarkdownViewer({ content, className }: MarkdownViewerProps) {
	const components: StreamdownProps["components"] = {
		// Define custom components for markdown elements
		callout: ({ children, ...props }) => (
			<div
				className="my-4 rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-950"
				{...props}
			>
				{children}
			</div>
		),
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
			<div className="overflow-x-auto my-4">
				<table className="min-w-full divide-y divide-border" {...props} />
			</div>
		),
		th: ({ ...props }) => <th className="px-3 py-2 text-left font-medium bg-muted" {...props} />,
		td: ({ ...props }) => <td className="px-3 py-2 border-t border-border" {...props} />,
		code: ({ className, children, ...props }) => {
			const match = /language-(\w+)/.exec(className || "");
			const isInline = !match;

			if (isInline) {
				return (
					<code className="bg-muted px-1 py-0.5 rounded text-xs" {...props}>
						{children}
					</code>
				);
			}

			// For code blocks, let Streamdown handle syntax highlighting
			return (
				<code className={className} {...props}>
					{children}
				</code>
			);
		},
	};

	return (
		<div
			className={cn(
				"prose prose-sm dark:prose-invert max-w-none overflow-hidden [&_pre]:overflow-x-auto [&_code]:wrap-break-word [&_table]:block [&_table]:overflow-x-auto",
				className
			)}
		>
			<Streamdown components={components} shikiTheme={["github-light", "github-dark"]}>
				{content}
			</Streamdown>
		</div>
	);
}
