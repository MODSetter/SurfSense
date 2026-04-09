"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { Info } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { updateSearchSpaceMutationAtom } from "@/atoms/search-spaces/search-space-mutation.atoms";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { PlateEditor } from "@/components/editor/plate-editor";
import { Spinner } from "@/components/ui/spinner";
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

	const handleMarkdownChange = useCallback((md: string) => {
		const trimmed = md.trim();
		setMemory(trimmed);
	}, []);

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
			<Alert className="bg-muted/50 py-3 md:py-4">
				<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
				<AlertDescription className="text-xs md:text-sm">
				SurfSense uses this shared memory to provide team-wide context across all conversations in this search space.
				</AlertDescription>
			</Alert>

			<div className="h-[340px] overflow-y-auto rounded-md border">
				<PlateEditor
					markdown={searchSpace?.shared_memory_md || ""}
					onMarkdownChange={handleMarkdownChange}
					preset="minimal"
					defaultEditing
					placeholder="Add team context here, such as decisions, conventions, key facts, or current priorities"
					variant="default"
					editorVariant="none"
					className="px-4 py-4 text-xs min-h-full"
				/>
			</div>

			<div className="flex items-center justify-between">
				<span className={`text-xs ${getCounterColor()}`}>
					{charCount.toLocaleString()} / {MEMORY_HARD_LIMIT.toLocaleString()} characters
					{charCount > 20_000 && charCount <= MEMORY_HARD_LIMIT && " — Approaching limit"}
					{isOverLimit && " — Exceeds limit"}
				</span>
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
				className="relative gap-2 bg-white text-black hover:bg-neutral-100 dark:bg-white dark:text-black dark:hover:bg-neutral-200 items-center justify-center"
			>
				<span className={saving ? "opacity-0" : ""}>Save</span>
				{saving && <Spinner size="sm" className="absolute" />}
				</Button>
			</div>
		</div>
	);
}
