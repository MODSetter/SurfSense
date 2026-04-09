"use client";

import { Info } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { PlateEditor } from "@/components/editor/plate-editor";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { baseApiService } from "@/lib/apis/base-api.service";

const MEMORY_HARD_LIMIT = 25_000;

const MemoryReadSchema = z.object({
	memory_md: z.string(),
});

export function MemoryContent() {
	const [memory, setMemory] = useState("");
	const [savedMemory, setSavedMemory] = useState("");
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);

	const fetchMemory = useCallback(async () => {
		try {
			setLoading(true);
			const data = await baseApiService.get("/api/v1/users/me/memory", MemoryReadSchema);
			setMemory(data.memory_md);
			setSavedMemory(data.memory_md);
		} catch {
			toast.error("Failed to load memory");
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchMemory();
	}, [fetchMemory]);

	const handleSave = async () => {
		try {
			setSaving(true);
			const data = await baseApiService.put("/api/v1/users/me/memory", MemoryReadSchema, {
				body: { memory_md: memory },
			});
			setSavedMemory(data.memory_md);
			toast.success("Memory saved");
		} catch {
			toast.error("Failed to save memory");
		} finally {
			setSaving(false);
		}
	};

	const handleClear = async () => {
		try {
			setSaving(true);
			const data = await baseApiService.put("/api/v1/users/me/memory", MemoryReadSchema, {
				body: { memory_md: "" },
			});
			setMemory(data.memory_md);
			setSavedMemory(data.memory_md);
			toast.success("Memory cleared");
		} catch {
			toast.error("Failed to clear memory");
		} finally {
			setSaving(false);
		}
	};

	const handleMarkdownChange = useCallback((md: string) => {
		const trimmed = md.trim();
		setMemory(trimmed);
	}, []);

	const hasChanges = memory !== savedMemory;
	const charCount = memory.length;
	const isOverLimit = charCount > MEMORY_HARD_LIMIT;

	const getCounterColor = () => {
		if (charCount > MEMORY_HARD_LIMIT) return "text-red-500";
		if (charCount > 15_000) return "text-orange-500";
		if (charCount > 10_000) return "text-yellow-500";
		return "text-muted-foreground";
	};

	if (loading) {
		return (
			<div className="flex items-center justify-center py-12">
				<Spinner size="md" className="text-muted-foreground" />
			</div>
		);
	}

	return (
		<div className="space-y-4">
			<Alert className="bg-muted/50 py-3 md:py-4">
				<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
				<AlertDescription className="text-xs md:text-sm">
					<p>
						SurfSense uses this personal memory to personalize your responses across all
						conversations. Supports <span className="font-medium">Markdown</span> formatting.
					</p>
				</AlertDescription>
			</Alert>

			<div className="h-[340px] overflow-y-auto rounded-md border">
				<PlateEditor
					markdown={savedMemory}
					onMarkdownChange={handleMarkdownChange}
					preset="minimal"
					defaultEditing
					placeholder="Add personal context here, such as your preferences, instructions, or facts about you"
					variant="default"
					editorVariant="none"
					className="px-4 py-4 text-xs min-h-full"
				/>
			</div>

			<div className="flex items-center justify-between">
				<span className={`text-xs ${getCounterColor()}`}>
					{charCount.toLocaleString()} / {MEMORY_HARD_LIMIT.toLocaleString()} characters
					{charCount > 15_000 && charCount <= MEMORY_HARD_LIMIT && " - Approaching limit"}
					{isOverLimit && " - Exceeds limit"}
				</span>
			</div>

			<div className="flex justify-between">
				<Button
					type="button"
					variant="destructive"
					size="sm"
					onClick={handleClear}
					disabled={saving || !savedMemory}
				>
					Clear All
				</Button>
				<Button
					type="button"
					variant="outline"
					onClick={handleSave}
					disabled={saving || !hasChanges || isOverLimit}
					className="relative gap-2 bg-white text-black hover:bg-neutral-100 dark:bg-white dark:text-black dark:hover:bg-neutral-200 items-center justify-center"
				>
					<span className={saving ? "opacity-0" : ""}>Save</span>
					{saving && <Spinner size="sm" className="absolute" />}
				</Button>
			</div>
		</div>
	);
}
