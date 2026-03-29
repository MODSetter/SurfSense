"use client";

import { ChevronDown, ChevronRight, Folder, FolderOpen, Home } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { FolderDisplay } from "./FolderNode";

interface FolderPickerDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	folders: FolderDisplay[];
	title: string;
	description?: string;
	disabledFolderIds?: Set<number>;
	onSelect: (folderId: number | null) => void;
}

export function FolderPickerDialog({
	open,
	onOpenChange,
	folders,
	title,
	description,
	disabledFolderIds,
	onSelect,
}: FolderPickerDialogProps) {
	const [selectedId, setSelectedId] = useState<number | null>(null);
	const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

	useEffect(() => {
		if (open) {
			setSelectedId(null);
			setExpandedIds(new Set());
		}
	}, [open]);

	const foldersByParent = useMemo(() => {
		const map: Record<string, FolderDisplay[]> = {};
		for (const f of folders) {
			const key = f.parentId ?? "root";
			if (!map[key]) map[key] = [];
			map[key].push(f);
		}
		return map;
	}, [folders]);

	const toggleExpand = useCallback((id: number) => {
		setExpandedIds((prev) => {
			const next = new Set(prev);
			if (next.has(id)) next.delete(id);
			else next.add(id);
			return next;
		});
	}, []);

	const handleConfirm = useCallback(() => {
		onSelect(selectedId);
		onOpenChange(false);
	}, [selectedId, onSelect, onOpenChange]);

	function renderPickerLevel(parentId: number | null, depth: number): React.ReactNode[] {
		const key = parentId ?? "root";
		const children = (foldersByParent[key] ?? [])
			.slice()
			.sort((a, b) => a.position.localeCompare(b.position));

		return children.flatMap((f) => {
			const isDisabled = disabledFolderIds?.has(f.id) ?? false;
			const isExpanded = expandedIds.has(f.id);
			const hasChildren = (foldersByParent[f.id] ?? []).length > 0;
			const isSelected = selectedId === f.id;
			const FolderIcon = isExpanded ? FolderOpen : Folder;

			return [
				<button
					key={f.id}
					type="button"
					disabled={isDisabled}
					className={cn(
						"flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-sm transition-colors",
						isSelected && "bg-accent text-accent-foreground",
						!isSelected && !isDisabled && "hover:bg-accent/50",
						isDisabled && "cursor-not-allowed opacity-40"
					)}
					style={{ paddingLeft: `${depth * 16 + 8}px` }}
					onClick={() => {
						if (!isDisabled) setSelectedId(f.id);
					}}
				>
					{hasChildren ? (
						<button
							type="button"
							className="flex h-4 w-4 shrink-0 items-center justify-center"
							onClick={(e) => {
								e.stopPropagation();
								toggleExpand(f.id);
							}}
						>
							{isExpanded ? (
								<ChevronDown className="h-3.5 w-3.5" />
							) : (
								<ChevronRight className="h-3.5 w-3.5" />
							)}
						</button>
					) : (
						<span className="h-4 w-4 shrink-0" />
					)}
					<FolderIcon className="h-4 w-4 shrink-0 text-muted-foreground" />
					<span className="truncate">{f.name}</span>
				</button>,
				...(isExpanded ? renderPickerLevel(f.id, depth + 1) : []),
			];
		});
	}

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="select-none max-w-[90vw] sm:max-w-sm p-4 sm:p-5 data-[state=open]:animate-none data-[state=closed]:animate-none">
				<DialogHeader className="space-y-2 pb-2">
					<div className="flex items-center gap-2 sm:gap-3">
						<div className="flex-1 min-w-0">
							<DialogTitle className="text-base sm:text-lg">{title}</DialogTitle>
							{description && (
								<DialogDescription className="text-xs sm:text-sm mt-0.5">
									{description}
								</DialogDescription>
							)}
						</div>
					</div>
				</DialogHeader>

				<div className="max-h-[300px] overflow-y-auto rounded-md border p-1">
					<button
						type="button"
						className={cn(
							"flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-sm transition-colors",
							selectedId === null && "bg-accent text-accent-foreground",
							selectedId !== null && "hover:bg-accent/50"
						)}
						onClick={() => setSelectedId(null)}
					>
						<span className="h-4 w-4 shrink-0" />
						<Home className="h-4 w-4 shrink-0 text-muted-foreground" />
						<span>Root</span>
					</button>
					{renderPickerLevel(null, 1)}
				</div>

				<DialogFooter className="flex-row justify-end gap-2 pt-2 sm:pt-3">
					<Button
						variant="secondary"
						onClick={() => onOpenChange(false)}
						className="h-8 sm:h-9 text-xs sm:text-sm"
					>
						Cancel
					</Button>
					<Button onClick={handleConfirm} className="h-8 sm:h-9 text-xs sm:text-sm">
						Move here
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
