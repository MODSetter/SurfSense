"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
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

	const hasChanges = memory !== savedMemory;
	const charCount = memory.length;
	const isOverLimit = charCount > MEMORY_HARD_LIMIT;

	const getCounterColor = () => {
		if (charCount > MEMORY_HARD_LIMIT) return "text-red-500";
		if (charCount > 20_000) return "text-orange-500";
		if (charCount > 15_000) return "text-yellow-500";
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
			<div className="rounded-lg border bg-card p-6">
				<div className="space-y-4">
					<div>
						<Label htmlFor="user-memory">Personal Memory</Label>
						<p className="mt-1 text-xs text-muted-foreground">
							This is your personal memory document. The AI assistant reads it at the start of
							every conversation and uses it to personalize responses. You can edit it directly
							or let the assistant update it during conversations.
						</p>
					</div>

					<Textarea
						id="user-memory"
						value={memory}
						onChange={(e) => setMemory(e.target.value)}
						placeholder={"## About me\n- ...\n\n## Preferences\n- ...\n\n## Instructions\n- ..."}
						className="min-h-[300px] font-mono text-sm"
					/>

					<div className="flex items-center justify-between">
						<span className={`text-xs ${getCounterColor()}`}>
							{charCount.toLocaleString()} / {MEMORY_HARD_LIMIT.toLocaleString()} characters
							{charCount > 20_000 && charCount <= MEMORY_HARD_LIMIT && " — Approaching limit"}
							{isOverLimit && " — Exceeds limit"}
						</span>
					</div>
				</div>
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
					className="gap-2 bg-white text-black hover:bg-neutral-100 dark:bg-white dark:text-black dark:hover:bg-neutral-200"
				>
					{saving && <Spinner size="sm" className="mr-2" />}
					Save
				</Button>
			</div>
		</div>
	);
}
