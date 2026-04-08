"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { updateSearchSpaceMutationAtom } from "@/atoms/search-spaces/search-space-mutation.atoms";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

const MEMORY_HARD_LIMIT = 25_000;

interface TeamMemoryManagerProps {
	searchSpaceId: number;
}

export function TeamMemoryManager({ searchSpaceId }: TeamMemoryManagerProps) {
	const {
		data: searchSpace,
		isLoading: loading,
	} = useQuery({
		queryKey: cacheKeys.searchSpaces.detail(searchSpaceId.toString()),
		queryFn: () => searchSpacesApiService.getSearchSpace({ id: searchSpaceId }),
		enabled: !!searchSpaceId,
	});

	const { mutateAsync: updateSearchSpace } = useAtomValue(updateSearchSpaceMutationAtom);

	const [memory, setMemory] = useState("");
	const [saving, setSaving] = useState(false);

	useEffect(() => {
		if (searchSpace) {
			setMemory(searchSpace.shared_memory_md || "");
		}
	}, [searchSpace?.shared_memory_md]);

	const hasChanges =
		!!searchSpace &&
		(searchSpace.shared_memory_md || "") !== memory;

	const handleSave = async () => {
		try {
			setSaving(true);
			await updateSearchSpace({
				id: searchSpaceId,
				data: { shared_memory_md: memory },
			});
			toast.success("Team memory saved");
		} catch {
			toast.error("Failed to save team memory");
		} finally {
			setSaving(false);
		}
	};

	const handleClear = async () => {
		try {
			setSaving(true);
			await updateSearchSpace({
				id: searchSpaceId,
				data: { shared_memory_md: "" },
			});
			setMemory("");
			toast.success("Team memory cleared");
		} catch {
			toast.error("Failed to clear team memory");
		} finally {
			setSaving(false);
		}
	};

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
						<Label htmlFor="team-memory">Team Memory</Label>
						<p className="mt-1 text-xs text-muted-foreground">
							This is the shared memory document for this search space. The AI assistant reads
							it at the start of every conversation and uses it for team-wide context. You can
							edit it directly or let the assistant update it during conversations.
						</p>
					</div>

					<Textarea
						id="team-memory"
						value={memory}
						onChange={(e) => setMemory(e.target.value)}
						placeholder={
							"## Team decisions\n- ...\n\n## Conventions\n- ...\n\n## Key facts\n- ...\n\n## Current priorities\n- ..."
						}
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
					disabled={saving || !(searchSpace?.shared_memory_md)}
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
