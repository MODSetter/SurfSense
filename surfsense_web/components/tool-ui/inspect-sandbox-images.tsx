"use client";

import { ChevronRightIcon, EyeIcon, Loader2Icon } from "lucide-react";
import { useState } from "react";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import type { TimelineToolProps } from "@/features/chat-messages/timeline/tool-registry/types";
import { cn } from "@/lib/utils";

function resultText(result: unknown): string {
	if (typeof result === "string") return result;
	if (result && typeof result === "object") {
		const value = result as Record<string, unknown>;
		if (typeof value.result === "string") return value.result;
		if (typeof value.output === "string") return value.output;
		if (typeof value.error === "string") return value.error;
	}
	return "";
}

export function InspectSandboxImagesToolUI({ args, result, status }: TimelineToolProps) {
	const [open, setOpen] = useState(false);
	const paths = Array.isArray(args.paths)
		? args.paths.filter((path) => typeof path === "string")
		: [];
	const mode = args.mode === "together" ? "together" : "each";

	if (status === "pending" || status === "running") {
		return (
			<div
				className="my-4 flex max-w-lg items-center gap-3 rounded-xl border bg-card px-4 py-3"
				aria-busy="true"
			>
				<Loader2Icon className="size-4 animate-spin text-muted-foreground" />
				<span className="text-sm text-muted-foreground">
					{mode === "together" ? "Comparing pages" : "Inspecting pages"}
				</span>
				<Badge variant="outline" className="ml-auto">
					{paths.length}
				</Badge>
			</div>
		);
	}

	const findings = resultText(result);
	return (
		<div className="my-4 max-w-lg">
			<Collapsible open={open} onOpenChange={setOpen}>
				<CollapsibleTrigger
					className={cn(
						"flex w-full items-center gap-2 rounded-xl border bg-card px-4 py-2.5 text-left transition-colors hover:bg-accent",
						open && "rounded-b-none border-b-0"
					)}
				>
					<ChevronRightIcon
						className={cn(
							"size-3.5 text-muted-foreground transition-transform",
							open && "rotate-90"
						)}
					/>
					<EyeIcon className="size-3.5 text-muted-foreground" />
					<span className="min-w-0 flex-1 truncate text-sm">
						{mode === "together" ? "Cross-page consistency" : "Page review"}
					</span>
					<Badge variant="outline">{paths.length}</Badge>
				</CollapsibleTrigger>
				<CollapsibleContent>
					<div className="max-h-96 overflow-auto rounded-b-xl border border-t-0 bg-muted/20 px-4 py-3">
						{findings ? (
							<MarkdownViewer content={findings} />
						) : (
							<output className="text-sm text-muted-foreground">No findings were returned.</output>
						)}
					</div>
				</CollapsibleContent>
			</Collapsible>
		</div>
	);
}
