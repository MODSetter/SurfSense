"use client";

import { CheckIcon, CopyIcon } from "lucide-react";
import mermaid from "mermaid";
import { memo, type ReactNode, useEffect, useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { copyToClipboard } from "@/lib/utils";

type MermaidDiagramProps = {
	source: string;
	isDarkMode: boolean;
	fallback: ReactNode;
};

let mermaidInitialized = false;

function initializeMermaid() {
	if (mermaidInitialized) return;

	mermaid.initialize({
		startOnLoad: false,
		securityLevel: "strict",
		htmlLabels: false,
		flowchart: { htmlLabels: false },
		sequence: { useMaxWidth: true },
	});

	mermaidInitialized = true;
}

function MermaidDiagramComponent({
	source,
	isDarkMode,
	fallback,
}: MermaidDiagramProps) {
	const id = useId();
	const [svg, setSvg] = useState<string | null>(null);
	const [hasError, setHasError] = useState(false);
	const [hasCopied, setHasCopied] = useState(false);

	useEffect(() => {
		let isCurrent = true;

		const renderId = `mermaid-${id.replace(/[^a-zA-Z0-9_-]/g, "")}`;

		setSvg(null);
		setHasError(false);

		(async () => {
			try {
				initializeMermaid();

				// فقط theme اینجا تنظیم میشه (نه re-init کامل)
				mermaid.initialize({
					startOnLoad: false,
					securityLevel: "strict",
					htmlLabels: false,
					theme: isDarkMode ? "dark" : "default",
					flowchart: { htmlLabels: false },
					sequence: { useMaxWidth: true },
				});

				await mermaid.parse(source);

				const { svg } = await mermaid.render(renderId, source);

				if (isCurrent) {
					setSvg(svg);
				}
			} catch (error) {
				console.error("[mermaid] Failed to render diagram", error);

				if (isCurrent) {
					setHasError(true);
				}
			}
		})();

		return () => {
			isCurrent = false;
		};
	}, [id, isDarkMode, source]);

	useEffect(() => {
		if (!hasCopied) return;

		const timer = setTimeout(() => setHasCopied(false), 2000);
		return () => clearTimeout(timer);
	}, [hasCopied]);

	if (hasError) return fallback;

	return (
		<div className="mt-4 overflow-hidden rounded-md bg-accent">
			<div className="flex items-center justify-between gap-4 px-4 py-2 text-sm font-semibold text-muted-foreground">
				<span className="text-xs lowercase">mermaid</span>

				<Button
					variant="ghost"
					size="sm"
					className="h-8 w-8 p-0"
					type="button"
					onClick={async () => {
						const ok = await copyToClipboard(source);
						if (ok) setHasCopied(true);
					}}
					aria-label={hasCopied ? "Copied Mermaid source" : "Copy Mermaid source"}
				>
					<span className="sr-only">Copy Source</span>
					{hasCopied ? (
						<CheckIcon className="!size-3" />
					) : (
						<CopyIcon className="!size-3" />
					)}
				</Button>
			</div>

			<div className="bg-background/60 p-4 overflow-x-auto">
				{svg ? (
					// biome-ignore lint/performance/noImgElement: svg is in-memory string
					<img
						src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`}
						alt="Mermaid diagram"
						className="mx-auto h-auto max-w-full"
					/>
				) : (
					<div className="h-32 animate-pulse rounded bg-muted" />
				)}
			</div>
		</div>
	);
}

export const MermaidDiagram = memo(MermaidDiagramComponent);