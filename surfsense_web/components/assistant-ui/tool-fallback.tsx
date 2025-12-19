import type { ToolCallMessagePartComponent } from "@assistant-ui/react";
import { CheckIcon, ChevronDownIcon, ChevronUpIcon, XCircleIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const ToolFallback: ToolCallMessagePartComponent = ({
	toolName,
	argsText,
	result,
	status,
}) => {
	const [isCollapsed, setIsCollapsed] = useState(true);

	const isCancelled = status?.type === "incomplete" && status.reason === "cancelled";
	const cancelledReason =
		isCancelled && status.error
			? typeof status.error === "string"
				? status.error
				: JSON.stringify(status.error)
			: null;

	return (
		<div
			className={cn(
				"aui-tool-fallback-root mb-4 flex w-full flex-col gap-3 rounded-lg border py-3",
				isCancelled && "border-muted-foreground/30 bg-muted/30"
			)}
		>
			<div className="aui-tool-fallback-header flex items-center gap-2 px-4">
				{isCancelled ? (
					<XCircleIcon className="aui-tool-fallback-icon size-4 text-muted-foreground" />
				) : (
					<CheckIcon className="aui-tool-fallback-icon size-4" />
				)}
				<p
					className={cn(
						"aui-tool-fallback-title grow",
						isCancelled && "text-muted-foreground line-through"
					)}
				>
					{isCancelled ? "Cancelled tool: " : "Used tool: "}
					<b>{toolName}</b>
				</p>
				<Button onClick={() => setIsCollapsed(!isCollapsed)}>
					{isCollapsed ? <ChevronUpIcon /> : <ChevronDownIcon />}
				</Button>
			</div>
			{!isCollapsed && (
				<div className="aui-tool-fallback-content flex flex-col gap-2 border-t pt-2">
					{cancelledReason && (
						<div className="aui-tool-fallback-cancelled-root px-4">
							<p className="aui-tool-fallback-cancelled-header font-semibold text-muted-foreground">
								Cancelled reason:
							</p>
							<p className="aui-tool-fallback-cancelled-reason text-muted-foreground">
								{cancelledReason}
							</p>
						</div>
					)}
					<div className={cn("aui-tool-fallback-args-root px-4", isCancelled && "opacity-60")}>
						<pre className="aui-tool-fallback-args-value whitespace-pre-wrap">{argsText}</pre>
					</div>
					{!isCancelled && result !== undefined && (
						<div className="aui-tool-fallback-result-root border-t border-dashed px-4 pt-2">
							<p className="aui-tool-fallback-result-header font-semibold">Result:</p>
							<pre className="aui-tool-fallback-result-content whitespace-pre-wrap">
								{typeof result === "string" ? result : JSON.stringify(result, null, 2)}
							</pre>
						</div>
					)}
				</div>
			)}
		</div>
	);
};
