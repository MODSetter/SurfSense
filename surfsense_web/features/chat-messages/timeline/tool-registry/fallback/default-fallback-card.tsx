"use client";

import { CheckIcon, ChevronDownIcon, XCircleIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { NestedScroll } from "@/components/assistant-ui/nested-scroll";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { getToolDisplayName } from "@/contracts/enums/toolIcons";
import { cn } from "@/lib/utils";
import type { TimelineToolComponent } from "../types";
import { ToolCardRevertButton } from "./revert-button";

/**
 * Best-effort error/cancellation reason from a tool result. Used as
 * the card subtitle when ``status`` is "error" or "cancelled". Returns
 * ``null`` if no usable text can be extracted.
 *
 * Tries: plain string → ``result.error`` → ``result.message`` →
 * stringified result. Per-tool components own richer error UIs; this
 * is the generic fallback's coarse summary.
 */
function deriveResultMessage(result: unknown): string | null {
	if (result == null) return null;
	if (typeof result === "string") return result;
	if (typeof result !== "object") return null;
	const r = result as { error?: unknown; message?: unknown };
	if (typeof r.error === "string") return r.error;
	if (typeof r.message === "string") return r.message;
	try {
		return JSON.stringify(result);
	} catch {
		return null;
	}
}

/**
 * Compact tool-call card. Used by ``FallbackToolBody`` for unregistered
 * tools whose result is not an HITL interrupt.
 *
 * shadcn composition note: ``Card`` is used as a visual frame WITHOUT
 * ``CardHeader``/``CardContent`` — the full composition's ``p-6``
 * doesn't fit a compact collapsible header that IS the trigger.
 *
 * Per-card expansion auto-syncs to ``isRunning`` (auto-expand on
 * stream start, auto-collapse on completion); manual toggle takes over
 * once streaming ends.
 */
export const DefaultFallbackCard: TimelineToolComponent = ({
	toolCallId,
	toolName,
	argsText,
	result,
	status,
	langchainToolCallId,
}) => {
	const isCancelled = status === "cancelled";
	const isError = status === "error";
	const isRunning = status === "running";

	const [isExpanded, setIsExpanded] = useState(isRunning);
	useEffect(() => {
		setIsExpanded(isRunning);
	}, [isRunning]);

	const serializedResult = useMemo(
		() =>
			result !== undefined && typeof result !== "string" ? JSON.stringify(result, null, 2) : null,
		[result]
	);

	const subtitle = useMemo(
		() => (isError || isCancelled ? deriveResultMessage(result) : null),
		[isError, isCancelled, result]
	);

	const displayName = getToolDisplayName(toolName);

	return (
		<Card
			className={cn(
				"my-4 max-w-lg overflow-hidden",
				isCancelled && "opacity-60",
				isError && "border-destructive/30"
			)}
		>
			<Collapsible
				className="group"
				open={isExpanded}
				onOpenChange={(next) => {
					if (isRunning) return;
					setIsExpanded(next);
				}}
			>
				<div className="flex items-stretch transition-colors hover:bg-muted/50">
					<CollapsibleTrigger asChild>
						<button
							type="button"
							className={cn(
								"flex flex-1 min-w-0 items-center gap-3 py-4 pl-5 pr-2 text-left",
								"focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
								"disabled:cursor-default"
							)}
						>
							<div
								className={cn(
									"flex size-8 shrink-0 items-center justify-center rounded-lg",
									isError ? "bg-destructive/10" : isCancelled ? "bg-muted" : "bg-primary/10"
								)}
							>
								{isError ? (
									<XCircleIcon className="size-4 text-destructive" />
								) : isCancelled ? (
									<XCircleIcon className="size-4 text-muted-foreground" />
								) : isRunning ? (
									<Spinner size="sm" className="text-primary" />
								) : (
									<CheckIcon className="size-4 text-primary" />
								)}
							</div>

							<div className="flex flex-1 min-w-0 flex-col gap-0.5">
								<div className="flex items-center gap-2">
									<p
										className={cn(
											"text-sm font-semibold truncate",
											isCancelled && "text-muted-foreground line-through",
											isError && "text-destructive"
										)}
									>
										{displayName}
									</p>
									{isRunning && <Badge variant="secondary">Running</Badge>}
									{isError && <Badge variant="destructive">Failed</Badge>}
									{isCancelled && <Badge variant="outline">Cancelled</Badge>}
								</div>
								{subtitle && (
									<p
										className={cn(
											"text-xs truncate",
											isError ? "text-destructive/80" : "text-muted-foreground"
										)}
									>
										{subtitle}
									</p>
								)}
							</div>
						</button>
					</CollapsibleTrigger>

					<div className="flex shrink-0 items-center gap-2 pl-2 pr-5">
						<ToolCardRevertButton
							toolCallId={toolCallId}
							toolName={toolName}
							langchainToolCallId={langchainToolCallId}
						/>
						<CollapsibleTrigger asChild>
							<Button
								type="button"
								variant="ghost"
								size="icon"
								aria-label={isExpanded ? "Collapse details" : "Expand details"}
								className="size-7 shrink-0"
							>
								<ChevronDownIcon
									className={cn(
										"size-4 transition-transform duration-200",
										"group-data-[state=open]:rotate-180"
									)}
								/>
							</Button>
						</CollapsibleTrigger>
					</div>
				</div>

				<CollapsibleContent>
					<Separator />
					<div className="flex flex-col gap-3 px-5 py-3">
						{(argsText || isRunning) && (
							<div className="flex flex-col gap-1 min-w-0">
								<p className="text-xs font-medium text-muted-foreground">Inputs</p>
								<NestedScroll className="max-h-48 overflow-auto rounded-md bg-muted/40">
									{argsText ? (
										<pre className="px-3 py-2 text-xs text-foreground/80 whitespace-pre-wrap break-all font-mono">
											{argsText}
										</pre>
									) : (
										<p className="px-3 py-2 text-xs italic text-muted-foreground">
											Waiting for input…
										</p>
									)}
								</NestedScroll>
							</div>
						)}
						{!isCancelled && result !== undefined && (
							<>
								<Separator />
								<div className="flex flex-col gap-1 min-w-0">
									<p className="text-xs font-medium text-muted-foreground">Result</p>
									<NestedScroll className="max-h-64 overflow-auto rounded-md bg-muted/40">
										<pre className="px-3 py-2 text-xs text-foreground/80 whitespace-pre-wrap break-all font-mono">
											{typeof result === "string" ? result : serializedResult}
										</pre>
									</NestedScroll>
								</div>
							</>
						)}
					</div>
				</CollapsibleContent>
			</Collapsible>
		</Card>
	);
};
