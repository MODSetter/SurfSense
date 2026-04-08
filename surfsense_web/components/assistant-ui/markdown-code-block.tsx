"use client";

import { CheckIcon, CopyIcon } from "lucide-react";
import type { CSSProperties } from "react";
import { memo, useEffect, useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { materialDark, materialLight } from "react-syntax-highlighter/dist/esm/styles/prism";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, copyToClipboard } from "@/lib/utils";

type MarkdownCodeBlockProps = {
	className?: string;
	language: string;
	codeText: string;
	isDarkMode: boolean;
};

function stripThemeBackgrounds(
	theme: Record<string, CSSProperties>
): Record<string, CSSProperties> {
	const cleaned: Record<string, CSSProperties> = {};
	for (const key of Object.keys(theme)) {
		const { background, backgroundColor, ...rest } = theme[key] as CSSProperties & {
			background?: string;
			backgroundColor?: string;
		};
		cleaned[key] = rest;
	}
	return cleaned;
}

const cleanMaterialDark = stripThemeBackgrounds(materialDark);
const cleanMaterialLight = stripThemeBackgrounds(materialLight);

function MarkdownCodeBlockComponent({
	className,
	language,
	codeText,
	isDarkMode,
}: MarkdownCodeBlockProps) {
	const [hasCopied, setHasCopied] = useState(false);

	useEffect(() => {
		if (!hasCopied) return;
		const timer = setTimeout(() => setHasCopied(false), 2000);
		return () => clearTimeout(timer);
	}, [hasCopied]);

	return (
		<div className="mt-4 overflow-hidden rounded-2xl" style={{ background: "var(--syntax-bg)" }}>
			<div className="flex items-center justify-between gap-4 px-4 py-2 font-semibold text-muted-foreground text-sm">
				<span className="lowercase text-xs">{language}</span>
				<Button
					variant="ghost"
					size="sm"
					className="h-8 w-8 p-0"
					type="button"
					onClick={async () => {
						const ok = await copyToClipboard(codeText);
						if (ok) setHasCopied(true);
					}}
					aria-label={hasCopied ? "Copied code" : "Copy code"}
				>
					<span className="sr-only">Copy</span>
					{hasCopied ? <CheckIcon className="!size-3" /> : <CopyIcon className="!size-3" />}
				</Button>
			</div>

			<SyntaxHighlighter
				style={isDarkMode ? cleanMaterialDark : cleanMaterialLight}
				language={language}
				PreTag="div"
				customStyle={{ margin: 0, background: "transparent" }}
				className={cn(className)}
			>
				{codeText}
			</SyntaxHighlighter>
		</div>
	);
}

export const MarkdownCodeBlock = memo(MarkdownCodeBlockComponent);

export function MarkdownCodeBlockSkeleton() {
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
