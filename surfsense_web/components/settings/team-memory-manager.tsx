"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { Download, Info, Send } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { updateSearchSpaceMutationAtom } from "@/atoms/search-spaces/search-space-mutation.atoms";
import { PlateEditor } from "@/components/editor/plate-editor";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { baseApiService } from "@/lib/apis/base-api.service";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

const MEMORY_HARD_LIMIT = 25_000;

const SearchSpaceSchema = z
	.object({
		shared_memory_md: z.string().optional().default(""),
	})
	.passthrough();

interface TeamMemoryManagerProps {
	searchSpaceId: number;
}

export function TeamMemoryManager({ searchSpaceId }: TeamMemoryManagerProps) {
	const queryClient = useQueryClient();
	const { data: searchSpace, isLoading: loading } = useQuery({
		queryKey: cacheKeys.searchSpaces.detail(searchSpaceId.toString()),
		queryFn: () => searchSpacesApiService.getSearchSpace({ id: searchSpaceId }),
		enabled: !!searchSpaceId,
	});

	const { mutateAsync: updateSearchSpace } = useAtomValue(updateSearchSpaceMutationAtom);

	const [saving, setSaving] = useState(false);
	const [editQuery, setEditQuery] = useState("");
	const [editing, setEditing] = useState(false);
	const textareaRef = useRef<HTMLTextAreaElement>(null);

	const memory = searchSpace?.shared_memory_md || "";

	const handleClear = async () => {
		try {
			setSaving(true);
			await updateSearchSpace({
				id: searchSpaceId,
				data: { shared_memory_md: "" },
			});
			toast.success("Team memory cleared");
		} catch {
			toast.error("Failed to clear team memory");
		} finally {
			setSaving(false);
		}
	};

	const handleEdit = async () => {
		const query = editQuery.trim();
		if (!query) return;

		try {
			setEditing(true);
			await baseApiService.post(
				`/api/v1/searchspaces/${searchSpaceId}/memory/edit`,
				SearchSpaceSchema,
				{ body: { query } }
			);
			setEditQuery("");
			await queryClient.invalidateQueries({
				queryKey: cacheKeys.searchSpaces.detail(searchSpaceId.toString()),
			});
			toast.success("Team memory updated");
		} catch {
			toast.error("Failed to edit team memory");
		} finally {
			setEditing(false);
		}
	};

	const handleExport = () => {
		if (!memory) return;
		try {
			const blob = new Blob([memory], { type: "text/markdown;charset=utf-8" });
			const url = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = url;
			a.download = "team-memory.md";
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		} catch {
			toast.error("Failed to export team memory");
		}
	};

	const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			handleEdit();
		}
	};

	const displayMemory = memory.replace(/\(\d{4}-\d{2}-\d{2}\)\s*/g, "");
	const charCount = memory.length;

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

	if (!memory) {
		return (
			<div className="flex flex-col items-center justify-center py-16 text-center">
				<h3 className="text-base font-medium text-foreground">
					What does SurfSense remember about your team?
				</h3>
				<p className="mt-2 max-w-sm text-sm text-muted-foreground">
					Nothing yet. SurfSense picks up on team decisions and conventions as your team chats.
				</p>
			</div>
		);
	}

	return (
		<div className="space-y-4">
			<Alert className="bg-muted/50 py-3 md:py-4">
				<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
				<AlertDescription className="text-xs md:text-sm">
					<p>
						SurfSense uses this shared memory to provide team-wide context across all conversations
						in this search space. Use the input below to add, update, or remove memory entries.
					</p>
				</AlertDescription>
			</Alert>

			<div className="h-[340px] overflow-y-auto rounded-md border">
				<PlateEditor
					markdown={displayMemory}
					readOnly
					preset="readonly"
					variant="default"
					editorVariant="none"
					className="px-4 py-4 text-xs min-h-full"
				/>
			</div>

			<div className="flex items-center justify-between">
				<span className={`text-xs ${getCounterColor()}`}>
					{charCount.toLocaleString()} / {MEMORY_HARD_LIMIT.toLocaleString()} characters
					{charCount > 15_000 && charCount <= MEMORY_HARD_LIMIT && " - Approaching limit"}
					{charCount > MEMORY_HARD_LIMIT && " - Exceeds limit"}
				</span>
			</div>

			<div className="relative">
				<Textarea
					ref={textareaRef}
					value={editQuery}
					onChange={(e) => setEditQuery(e.target.value)}
					onKeyDown={handleKeyDown}
					placeholder="Tell SurfSense what to remember or forget about your team"
					disabled={editing}
					rows={2}
					className="pr-12 resize-none text-sm"
				/>
				<Button
					type="button"
					size="icon"
					variant="ghost"
					onClick={handleEdit}
					disabled={editing || !editQuery.trim()}
					className="absolute right-2 bottom-2 h-7 w-7"
				>
					{editing ? <Spinner size="sm" /> : <Send className="h-4 w-4" />}
				</Button>
			</div>

			<div className="flex items-center gap-2">
				<Button
					type="button"
					variant="destructive"
					size="sm"
					onClick={handleClear}
					disabled={saving || editing || !memory}
				>
					Clear Memory
				</Button>
				<Button
					type="button"
					variant="outline"
					size="sm"
					onClick={handleExport}
					disabled={!memory}
				>
					<Download className="h-4 w-4" />
					Export
				</Button>
			</div>
		</div>
	);
}
