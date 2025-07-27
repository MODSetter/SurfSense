"use client";

import { Check, Copy } from "lucide-react";
import { useTheme } from "next-themes";
import { memo, useCallback, useEffect, useMemo, useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/cjs/styles/prism";

// Constants for styling and configuration
const COPY_TIMEOUT = 2000;

const BASE_CUSTOM_STYLE = {
	margin: 0,
	borderRadius: "0.375rem",
	fontSize: "0.75rem",
	lineHeight: "1.5rem",
	border: "none",
} as const;

const LINE_PROPS_STYLE = {
	wordBreak: "break-all" as const,
	whiteSpace: "pre-wrap" as const,
	border: "none",
	borderBottom: "none",
	paddingLeft: 0,
	paddingRight: 0,
	margin: "0.25rem 0",
} as const;

const CODE_TAG_PROPS = {
	className: "font-mono",
	style: {
		border: "none",
		background: "var(--syntax-bg)",
	},
} as const;

// TypeScript interfaces
interface CodeBlockProps {
	children: string;
	language: string;
}

type LanguageRenderer = (props: { code: string }) => React.JSX.Element;

interface SyntaxStyle {
	[key: string]: React.CSSProperties;
}

// Memoized fallback component for SSR/hydration
const FallbackCodeBlock = memo(({ children }: { children: string }) => (
	<div className="bg-muted p-4 rounded-md">
		<pre className="m-0 p-0 border-0">
			<code className="text-xs font-mono border-0 leading-6">{children}</code>
		</pre>
	</div>
));

FallbackCodeBlock.displayName = "FallbackCodeBlock";

// Code block component with syntax highlighting and copy functionality
export const CodeBlock = memo<CodeBlockProps>(({ children, language }) => {
	const [copied, setCopied] = useState(false);
	const { resolvedTheme, theme } = useTheme();
	const [mounted, setMounted] = useState(false);

	// Prevent hydration issues
	useEffect(() => {
		setMounted(true);
	}, []);

	// Memoize theme detection
	const isDarkTheme = useMemo(
		() => mounted && (resolvedTheme === "dark" || theme === "dark"),
		[mounted, resolvedTheme, theme]
	);

	// Memoize syntax theme selection
	const syntaxTheme = useMemo(() => (isDarkTheme ? oneDark : oneLight), [isDarkTheme]);

	// Memoize enhanced style with theme-specific modifications
	const enhancedStyle = useMemo<SyntaxStyle>(
		() => ({
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
		}),
		[syntaxTheme]
	);

	// Memoize custom style with background
	const customStyle = useMemo(
		() => ({
			...BASE_CUSTOM_STYLE,
			backgroundColor: "var(--syntax-bg)",
		}),
		[]
	);

	// Memoized copy handler
	const handleCopy = useCallback(async () => {
		try {
			await navigator.clipboard.writeText(children);
			setCopied(true);
			const timeoutId = setTimeout(() => setCopied(false), COPY_TIMEOUT);
			return () => clearTimeout(timeoutId);
		} catch (error) {
			console.warn("Failed to copy code to clipboard:", error);
		}
	}, [children]);

	// Memoized line props with style
	const lineProps = useMemo(
		() => ({
			style: LINE_PROPS_STYLE,
		}),
		[]
	);

	// Early return for non-mounted state
	if (!mounted) {
		return <FallbackCodeBlock>{children}</FallbackCodeBlock>;
	}

	return (
		<div className="relative my-4 group">
			<div className="absolute right-2 top-2 z-10">
				<button
					onClick={handleCopy}
					className="p-1.5 rounded-md bg-background/80 hover:bg-background border border-border flex items-center justify-center transition-colors"
					aria-label="Copy code"
					type="button"
				>
					{copied ? (
						<Check size={14} className="text-green-500" />
					) : (
						<Copy size={14} className="text-muted-foreground" />
					)}
				</button>
			</div>
			<SyntaxHighlighter
				language={language || "text"}
				style={enhancedStyle}
				customStyle={customStyle}
				codeTagProps={CODE_TAG_PROPS}
				showLineNumbers={false}
				wrapLines={false}
				lineProps={lineProps}
				PreTag="div"
			>
				{children}
			</SyntaxHighlighter>
		</div>
	);
});

CodeBlock.displayName = "CodeBlock";

// Optimized language renderer factory with memoization
const createLanguageRenderer = (lang: string): LanguageRenderer => {
	const renderer = ({ code }: { code: string }) => <CodeBlock language={lang}>{code}</CodeBlock>;
	renderer.displayName = `LanguageRenderer(${lang})`;
	return renderer;
};

// Pre-defined supported languages for better maintainability
const SUPPORTED_LANGUAGES = [
	"javascript",
	"typescript",
	"python",
	"java",
	"csharp",
	"cpp",
	"c",
	"php",
	"ruby",
	"go",
	"rust",
	"swift",
	"kotlin",
	"scala",
	"sql",
	"json",
	"xml",
	"yaml",
	"bash",
	"shell",
	"powershell",
	"dockerfile",
	"html",
	"css",
	"scss",
	"less",
	"markdown",
	"text",
] as const;

// Generate language renderers efficiently
export const languageRenderers: Record<string, LanguageRenderer> = Object.fromEntries(
	SUPPORTED_LANGUAGES.map((lang) => [lang, createLanguageRenderer(lang)])
);
