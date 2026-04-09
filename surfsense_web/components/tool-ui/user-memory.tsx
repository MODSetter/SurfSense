"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { AlertTriangleIcon, BrainIcon, CheckIcon, Loader2Icon, XIcon } from "lucide-react";
import { z } from "zod";

// ============================================================================
// Zod Schemas for update_memory tool
// ============================================================================

const UpdateMemoryArgsSchema = z.object({
	updated_memory: z.string(),
});

const UpdateMemoryResultSchema = z.object({
	status: z.enum(["saved", "error"]),
	message: z.string().nullish(),
	warning: z.string().nullish(),
});

type UpdateMemoryArgs = z.infer<typeof UpdateMemoryArgsSchema>;
type UpdateMemoryResult = z.infer<typeof UpdateMemoryResultSchema>;

// ============================================================================
// Update Memory Tool UI
// ============================================================================

export const UpdateMemoryToolUI = ({
	result,
	status,
}: ToolCallMessagePartProps<UpdateMemoryArgs, UpdateMemoryResult>) => {
	const isRunning = status.type === "running" || status.type === "requires-action";
	const isComplete = status.type === "complete";
	const isError = result?.status === "error";

	if (isRunning) {
		return (
			<div className="my-3 flex items-center gap-3 rounded-lg border bg-card/60 px-4 py-3">
				<div className="flex size-8 items-center justify-center rounded-full bg-primary/10">
					<Loader2Icon className="size-4 animate-spin text-primary" />
				</div>
				<div className="flex-1">
					<span className="text-sm text-muted-foreground">Updating memory...</span>
				</div>
			</div>
		);
	}

	if (isError) {
		return (
			<div className="my-3 flex items-center gap-3 rounded-lg border border-destructive/20 bg-destructive/5 px-4 py-3">
				<div className="flex size-8 items-center justify-center rounded-full bg-destructive/10">
					<XIcon className="size-4 text-destructive" />
				</div>
				<div className="flex-1">
					<span className="text-sm text-destructive">Failed to update memory</span>
					{result?.message && <p className="mt-1 text-xs text-destructive/70">{result.message}</p>}
				</div>
			</div>
		);
	}

	if (isComplete && result?.status === "saved") {
		return (
			<div className="my-3 flex items-center gap-3 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
				<div className="flex size-8 items-center justify-center rounded-full bg-primary/10">
					<BrainIcon className="size-4 text-primary" />
				</div>
				<div className="flex-1 min-w-0">
					<div className="flex items-center gap-2">
						<CheckIcon className="size-3 text-green-500 shrink-0" />
						<span className="text-sm font-medium text-foreground">Memory updated</span>
					</div>
					{result.warning && (
						<div className="mt-1.5 flex items-start gap-1.5">
							<AlertTriangleIcon className="size-3 text-yellow-500 shrink-0 mt-0.5" />
							<p className="text-xs text-yellow-600 dark:text-yellow-400">{result.warning}</p>
						</div>
					)}
				</div>
			</div>
		);
	}

	return null;
};

// ============================================================================
// Exports
// ============================================================================

export {
	UpdateMemoryArgsSchema,
	UpdateMemoryResultSchema,
	type UpdateMemoryArgs,
	type UpdateMemoryResult,
};
