"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { BrainIcon, CheckIcon, Loader2Icon, SearchIcon, XIcon } from "lucide-react";
import { z } from "zod";

// ============================================================================
// Zod Schemas for save_memory tool
// ============================================================================

const SaveMemoryArgsSchema = z.object({
	content: z.string(),
	category: z.string().default("fact"),
});

const SaveMemoryResultSchema = z.object({
	status: z.enum(["saved", "error"]),
	memory_id: z.number().nullish(),
	memory_text: z.string().nullish(),
	category: z.string().nullish(),
	message: z.string().nullish(),
	error: z.string().nullish(),
});

type SaveMemoryArgs = z.infer<typeof SaveMemoryArgsSchema>;
type SaveMemoryResult = z.infer<typeof SaveMemoryResultSchema>;

// ============================================================================
// Zod Schemas for recall_memory tool
// ============================================================================

const RecallMemoryArgsSchema = z.object({
	query: z.string().nullish(),
	category: z.string().nullish(),
	top_k: z.number().default(5),
});

const MemoryItemSchema = z.object({
	id: z.number(),
	memory_text: z.string(),
	category: z.string(),
	updated_at: z.string().nullish(),
});

const RecallMemoryResultSchema = z.object({
	status: z.enum(["success", "error"]),
	count: z.number().nullish(),
	memories: z.array(MemoryItemSchema).nullish(),
	formatted_context: z.string().nullish(),
	error: z.string().nullish(),
});

type RecallMemoryArgs = z.infer<typeof RecallMemoryArgsSchema>;
type RecallMemoryResult = z.infer<typeof RecallMemoryResultSchema>;
type MemoryItem = z.infer<typeof MemoryItemSchema>;

// ============================================================================
// Category badge colors
// ============================================================================

const categoryColors: Record<string, string> = {
	preference: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
	fact: "bg-green-500/10 text-green-600 dark:text-green-400",
	instruction: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
	context: "bg-orange-500/10 text-orange-600 dark:text-orange-400",
};

function CategoryBadge({ category }: { category: string }) {
	const colorClass = categoryColors[category] || "bg-gray-500/10 text-gray-600 dark:text-gray-400";
	return (
		<span
			className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colorClass}`}
		>
			{category}
		</span>
	);
}

// ============================================================================
// Save Memory Tool UI
// ============================================================================

export const SaveMemoryToolUI = makeAssistantToolUI<SaveMemoryArgs, SaveMemoryResult>({
	toolName: "save_memory",
	render: function SaveMemoryUI({ args, result, status }) {
		const isRunning = status.type === "running" || status.type === "requires-action";
		const isComplete = status.type === "complete";
		const isError = result?.status === "error";

		// Parse args safely
		const parsedArgs = SaveMemoryArgsSchema.safeParse(args);
		const content = parsedArgs.success ? parsedArgs.data.content : "";
		const category = parsedArgs.success ? parsedArgs.data.category : "fact";

		// Loading state
		if (isRunning) {
			return (
				<div className="my-3 flex items-center gap-3 rounded-lg border bg-card/60 px-4 py-3">
					<div className="flex size-8 items-center justify-center rounded-full bg-primary/10">
						<Loader2Icon className="size-4 animate-spin text-primary" />
					</div>
					<div className="flex-1">
						<span className="text-sm text-muted-foreground">Saving to memory...</span>
					</div>
				</div>
			);
		}

		// Error state
		if (isError) {
			return (
				<div className="my-3 flex items-center gap-3 rounded-lg border border-destructive/20 bg-destructive/5 px-4 py-3">
					<div className="flex size-8 items-center justify-center rounded-full bg-destructive/10">
						<XIcon className="size-4 text-destructive" />
					</div>
					<div className="flex-1">
						<span className="text-sm text-destructive">Failed to save memory</span>
						{result?.error && <p className="mt-1 text-xs text-destructive/70">{result.error}</p>}
					</div>
				</div>
			);
		}

		// Success state
		if (isComplete && result?.status === "saved") {
			return (
				<div className="my-3 flex items-center gap-3 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
					<div className="flex size-8 items-center justify-center rounded-full bg-primary/10">
						<BrainIcon className="size-4 text-primary" />
					</div>
					<div className="flex-1 min-w-0">
						<div className="flex items-center gap-2">
							<CheckIcon className="size-3 text-green-500 shrink-0" />
							<span className="text-sm font-medium text-foreground">Memory saved</span>
							<CategoryBadge category={category} />
						</div>
						<p className="mt-1 truncate text-sm text-muted-foreground">{content}</p>
					</div>
				</div>
			);
		}

		// Default/incomplete state - show what's being saved
		if (content) {
			return (
				<div className="my-3 flex items-center gap-3 rounded-lg border bg-card/60 px-4 py-3">
					<div className="flex size-8 items-center justify-center rounded-full bg-muted">
						<BrainIcon className="size-4 text-muted-foreground" />
					</div>
					<div className="flex-1 min-w-0">
						<div className="flex items-center gap-2">
							<span className="text-sm text-muted-foreground">Saving memory</span>
							<CategoryBadge category={category} />
						</div>
						<p className="mt-1 truncate text-sm text-muted-foreground">{content}</p>
					</div>
				</div>
			);
		}

		return null;
	},
});

// ============================================================================
// Recall Memory Tool UI
// ============================================================================

export const RecallMemoryToolUI = makeAssistantToolUI<RecallMemoryArgs, RecallMemoryResult>({
	toolName: "recall_memory",
	render: function RecallMemoryUI({ args, result, status }) {
		const isRunning = status.type === "running" || status.type === "requires-action";
		const isComplete = status.type === "complete";
		const isError = result?.status === "error";

		// Parse args safely
		const parsedArgs = RecallMemoryArgsSchema.safeParse(args);
		const query = parsedArgs.success ? parsedArgs.data.query : null;

		// Loading state
		if (isRunning) {
			return (
				<div className="my-3 flex items-center gap-3 rounded-lg border bg-card/60 px-4 py-3">
					<div className="flex size-8 items-center justify-center rounded-full bg-primary/10">
						<Loader2Icon className="size-4 animate-spin text-primary" />
					</div>
					<div className="flex-1">
						<span className="text-sm text-muted-foreground">
							{query ? `Searching memories for "${query}"...` : "Recalling memories..."}
						</span>
					</div>
				</div>
			);
		}

		// Error state
		if (isError) {
			return (
				<div className="my-3 flex items-center gap-3 rounded-lg border border-destructive/20 bg-destructive/5 px-4 py-3">
					<div className="flex size-8 items-center justify-center rounded-full bg-destructive/10">
						<XIcon className="size-4 text-destructive" />
					</div>
					<div className="flex-1">
						<span className="text-sm text-destructive">Failed to recall memories</span>
						{result?.error && <p className="mt-1 text-xs text-destructive/70">{result.error}</p>}
					</div>
				</div>
			);
		}

		// Success state with memories
		if (isComplete && result?.status === "success") {
			const memories = result.memories || [];
			const count = result.count || 0;

			if (count === 0) {
				return (
					<div className="my-3 flex items-center gap-3 rounded-lg border bg-card/60 px-4 py-3">
						<div className="flex size-8 items-center justify-center rounded-full bg-muted">
							<SearchIcon className="size-4 text-muted-foreground" />
						</div>
						<span className="text-sm text-muted-foreground">No memories found</span>
					</div>
				);
			}

			return (
				<div className="my-3 rounded-lg border bg-card/60 px-4 py-3">
					<div className="flex items-center gap-2 mb-2">
						<BrainIcon className="size-4 text-primary" />
						<span className="text-sm font-medium text-foreground">
							Recalled {count} {count === 1 ? "memory" : "memories"}
						</span>
					</div>
					<div className="space-y-2">
						{memories.slice(0, 5).map((memory: MemoryItem) => (
							<div
								key={memory.id}
								className="flex items-start gap-2 rounded-md bg-muted/50 px-3 py-2"
							>
								<CategoryBadge category={memory.category} />
								<span className="text-sm text-muted-foreground flex-1">{memory.memory_text}</span>
							</div>
						))}
						{memories.length > 5 && (
							<p className="text-xs text-muted-foreground">...and {memories.length - 5} more</p>
						)}
					</div>
				</div>
			);
		}

		// Default/incomplete state
		if (query) {
			return (
				<div className="my-3 flex items-center gap-3 rounded-lg border bg-card/60 px-4 py-3">
					<div className="flex size-8 items-center justify-center rounded-full bg-muted">
						<SearchIcon className="size-4 text-muted-foreground" />
					</div>
					<span className="text-sm text-muted-foreground">Searching memories for "{query}"</span>
				</div>
			);
		}

		return null;
	},
});

// ============================================================================
// Exports
// ============================================================================

export {
	SaveMemoryArgsSchema,
	SaveMemoryResultSchema,
	RecallMemoryArgsSchema,
	RecallMemoryResultSchema,
	type SaveMemoryArgs,
	type SaveMemoryResult,
	type RecallMemoryArgs,
	type RecallMemoryResult,
	type MemoryItem,
};
