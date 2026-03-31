import type { ToolCallMessagePartComponent } from "@assistant-ui/react";
import { CheckIcon, ChevronDownIcon, ChevronUpIcon, XCircleIcon } from "lucide-react";
import { useState } from "react";
import { getToolIcon } from "@/contracts/enums/toolIcons";
import { cn } from "@/lib/utils";

function formatToolName(name: string): string {
	return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export const ToolFallback: ToolCallMessagePartComponent = ({
	toolName,
	argsText,
	result,
	status,
}) => {
	const [isExpanded, setIsExpanded] = useState(false);

	const isCancelled = status?.type === "incomplete" && status.reason === "cancelled";
	const isError = status?.type === "incomplete" && status.reason === "error";
	const isRunning = status?.type === "running" || status?.type === "requires-action";
	const cancelledReason =
		isCancelled && status.error
			? typeof status.error === "string"
				? status.error
				: JSON.stringify(status.error)
			: null;
	const errorReason =
		isError && status.error
			? typeof status.error === "string"
				? status.error
				: JSON.stringify(status.error)
			: null;

	const Icon = getToolIcon(toolName);
	const displayName = formatToolName(toolName);

	return (
		<div
			className={cn(
				"my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none",
				isCancelled && "opacity-60",
				isError && "border-destructive/20 bg-destructive/5"
			)}
		>
			<button
				type="button"
			onClick={() => setIsExpanded(prev => !prev)}
				className="flex w-full items-center gap-3 px-5 py-4 text-left transition-colors hover:bg-muted/50 focus:outline-none focus-visible:outline-none"
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
						<Icon className="size-4 text-primary animate-pulse" />
					) : (
						<CheckIcon className="size-4 text-primary" />
					)}
				</div>

				<div className="flex-1 min-w-0">
					<p
						className={cn(
							"text-sm font-semibold",
							isError
								? "text-destructive"
								: isCancelled
									? "text-muted-foreground line-through"
									: "text-foreground"
						)}
					>
						{isRunning
							? displayName
							: isCancelled
								? `Cancelled: ${displayName}`
								: isError
									? `Failed: ${displayName}`
									: displayName}
					</p>
					{isRunning && <p className="text-xs text-muted-foreground mt-0.5">Running...</p>}
					{cancelledReason && (
						<p className="text-xs text-muted-foreground mt-0.5 truncate">{cancelledReason}</p>
					)}
					{errorReason && (
						<p className="text-xs text-destructive/80 mt-0.5 truncate">{errorReason}</p>
					)}
				</div>

				{!isRunning && (
					<div className="shrink-0 text-muted-foreground">
						{isExpanded ? (
							<ChevronDownIcon className="size-4" />
						) : (
							<ChevronUpIcon className="size-4" />
						)}
					</div>
				)}
			</button>

			{isExpanded && !isRunning && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-3 space-y-3">
						{argsText && (
							<div>
								<p className="text-xs font-medium text-muted-foreground mb-1">Arguments</p>
								<pre className="text-xs text-foreground/80 whitespace-pre-wrap break-all">
									{argsText}
								</pre>
							</div>
						)}
						{!isCancelled && result !== undefined && (
							<>
								<div className="h-px bg-border/30" />
								<div>
									<p className="text-xs font-medium text-muted-foreground mb-1">Result</p>
									<pre className="text-xs text-foreground/80 whitespace-pre-wrap break-all">
										{typeof result === "string" ? result : JSON.stringify(result, null, 2)}
									</pre>
								</div>
							</>
						)}
					</div>
				</>
			)}
		</div>
	);
};
