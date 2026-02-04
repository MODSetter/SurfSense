"use client";

import { useSetAtom } from "jotai";
import {
	CircleAlert,
	CircleX,
	Columns3,
	FilePlus2,
	FileType,
	SlidersHorizontal,
	Trash,
} from "lucide-react";
import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import React, { useMemo, useRef } from "react";
import { connectorDialogOpenAtom } from "@/atoms/connector-dialog/connector-dialog.atoms";
import { useDocumentUploadDialog } from "@/components/assistant-ui/document-upload-popup";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
	AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { getDocumentTypeIcon, getDocumentTypeLabel } from "./DocumentTypeIcon";
import type { ColumnVisibility } from "./types";

export function DocumentsFilters({
	typeCounts: typeCountsRecord,
	selectedIds,
	onSearch,
	searchValue,
	onBulkDelete,
	onToggleType,
	activeTypes,
	columnVisibility,
	onToggleColumn,
}: {
	typeCounts: Partial<Record<DocumentTypeEnum, number>>;
	selectedIds: Set<number>;
	onSearch: (v: string) => void;
	searchValue: string;
	onBulkDelete: () => Promise<void>;
	onToggleType: (type: DocumentTypeEnum, checked: boolean) => void;
	activeTypes: DocumentTypeEnum[];
	columnVisibility: ColumnVisibility;
	onToggleColumn: (id: keyof ColumnVisibility, checked: boolean) => void;
}) {
	const t = useTranslations("documents");
	const id = React.useId();
	const inputRef = useRef<HTMLInputElement>(null);

	// Dialog hooks for action buttons
	const { openDialog: openUploadDialog } = useDocumentUploadDialog();
	const setConnectorDialogOpen = useSetAtom(connectorDialogOpenAtom);

	const uniqueTypes = useMemo(() => {
		return Object.keys(typeCountsRecord).sort() as DocumentTypeEnum[];
	}, [typeCountsRecord]);

	const typeCounts = useMemo(() => {
		const map = new Map<string, number>();
		for (const [type, count] of Object.entries(typeCountsRecord)) {
			map.set(type, count);
		}
		return map;
	}, [typeCountsRecord]);

	return (
		<motion.div
			className="flex flex-col gap-4"
			initial={{ opacity: 0, y: 10 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ type: "spring", stiffness: 300, damping: 30, delay: 0.1 }}
		>
			{/* Main toolbar row */}
			<div className="flex flex-wrap items-center gap-3">
				{/* Action Buttons - Left Side */}
				<div className="flex items-center gap-2">
					<Button
						onClick={openUploadDialog}
						variant="outline"
						size="sm"
						className="h-9 gap-2 bg-white text-gray-700 border-white hover:bg-gray-50 dark:bg-white dark:text-gray-800 dark:hover:bg-gray-100"
					>
						<FilePlus2 size={16} />
						<span>Upload documents</span>
					</Button>
					<Button
						onClick={() => setConnectorDialogOpen(true)}
						variant="outline"
						size="sm"
						className="h-9 gap-2 bg-white text-gray-700 border-white hover:bg-gray-50 dark:bg-white dark:text-gray-800 dark:hover:bg-gray-100"
					>
						<SlidersHorizontal size={16} />
						<span>Manage connectors</span>
					</Button>
				</div>

				{/* Spacer */}
				<div className="flex-1" />

				{/* Search Input */}
				<motion.div
					className="relative w-[180px]"
					initial={{ opacity: 0, y: -10 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ type: "spring", stiffness: 300, damping: 30 }}
				>
					<Input
						id={`${id}-input`}
						ref={inputRef}
						className="peer h-9 w-full pl-3 pr-9 text-sm bg-background border-border/60 focus-visible:ring-1 focus-visible:ring-ring/30"
						value={searchValue}
						onChange={(e) => onSearch(e.target.value)}
						placeholder="Filter by title"
						type="text"
						aria-label={t("filter_placeholder")}
					/>
					{Boolean(searchValue) && (
						<motion.button
							className="absolute inset-y-0 right-0 flex h-full w-9 items-center justify-center rounded-r-md text-muted-foreground/60 hover:text-foreground transition-colors"
							aria-label="Clear filter"
							onClick={() => {
								onSearch("");
								inputRef.current?.focus();
							}}
							initial={{ opacity: 0, scale: 0.8 }}
							animate={{ opacity: 1, scale: 1 }}
							exit={{ opacity: 0, scale: 0.8 }}
							whileHover={{ scale: 1.1 }}
							whileTap={{ scale: 0.9 }}
						>
							<CircleX size={14} strokeWidth={2} aria-hidden="true" />
						</motion.button>
					)}
				</motion.div>

				{/* Filter Buttons Group */}
				<div className="flex items-center gap-2 flex-wrap">
					{/* Type Filter */}
					<Popover>
						<PopoverTrigger asChild>
							<Button
								variant="outline"
								size="sm"
								className="h-9 gap-2 border-dashed border-border/60 text-muted-foreground hover:text-foreground hover:border-border"
							>
								<FileType size={14} className="text-muted-foreground" />
								<span className="hidden sm:inline">Type</span>
								{activeTypes.length > 0 && (
									<span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-medium text-primary-foreground">
										{activeTypes.length}
									</span>
								)}
							</Button>
						</PopoverTrigger>
						<PopoverContent className="w-64 !p-0 overflow-hidden" align="end">
							<div className="px-2.5 pt-3">
								<div className="mb-1.5 px-1 text-[11px] font-medium text-muted-foreground">
									Filter by source
								</div>
								<div className="space-y-0.5 max-h-[300px] overflow-y-auto overflow-x-hidden">
									{uniqueTypes.map((value: DocumentTypeEnum, i) => (
										<button
											key={value}
											type="button"
											className="flex w-full items-center gap-2 py-1 px-2.5 rounded-md hover:bg-muted/50 transition-colors cursor-pointer text-left"
											onClick={() => onToggleType(value, !activeTypes.includes(value))}
										>
											<Checkbox
												id={`${id}-${i}`}
												checked={activeTypes.includes(value)}
												onCheckedChange={(checked: boolean) => onToggleType(value, !!checked)}
												className="h-3.5 w-3.5 flex-shrink-0 data-[state=checked]:bg-primary data-[state=checked]:border-primary"
											/>
											<Label
												htmlFor={`${id}-${i}`}
												className="flex flex-1 items-center gap-2 font-normal text-xs cursor-pointer min-w-0"
											>
												<span className="opacity-60 flex-shrink-0">{getDocumentTypeIcon(value)}</span>
												<span className="truncate min-w-0">{getDocumentTypeLabel(value)}</span>
												<span className="text-[10px] text-muted-foreground/70 tabular-nums flex-shrink-0 ml-auto">
													{typeCounts.get(value)}
												</span>
											</Label>
										</button>
									))}
								</div>
								{activeTypes.length > 0 && (
									<div className="mt-1 pt-1 pb-1 border-t border-border/50 pb-1">
										<Button
											variant="ghost"
											size="sm"
											className="w-full h-6 text-[11px]"
											onClick={() => {
												activeTypes.forEach((t) => {
													onToggleType(t, false);
												});
											}}
										>
											Clear filters
										</Button>
									</div>
								)}
							</div>
						</PopoverContent>
					</Popover>

					{/* View/Columns Popover */}
					<Popover>
						<PopoverTrigger asChild>
							<Button
								variant="outline"
								size="sm"
								className="h-9 gap-2 border-dashed border-border/60 text-muted-foreground hover:text-foreground hover:border-border"
							>
								<Columns3 size={14} className="text-muted-foreground" />
								<span className="hidden sm:inline">View</span>
							</Button>
						</PopoverTrigger>
						<PopoverContent className="w-36 !p-0 overflow-hidden" align="end">
							<div className="px-2.5 pt-3 pb-2">
								<div className="mb-1.5 px-1 text-[11px] font-medium text-muted-foreground">
									Toggle columns
								</div>
								<div className="space-y-0.5">
									{(
										[
											["document_type", "Source"],
											["created_by", "User"],
											["created_at", "Created"],
										] as Array<[keyof ColumnVisibility, string]>
									).map(([key, label], i) => (
										<button
											key={key}
											type="button"
											className="flex w-full items-center gap-2 py-1 px-2.5 rounded-md hover:bg-muted/50 transition-colors cursor-pointer text-left"
											onClick={() => onToggleColumn(key, !columnVisibility[key])}
										>
											<Checkbox
												id={`${id}-col-${i}`}
												checked={columnVisibility[key]}
												onCheckedChange={(checked: boolean) => onToggleColumn(key, !!checked)}
												className="h-3.5 w-3.5 flex-shrink-0 data-[state=checked]:bg-primary data-[state=checked]:border-primary"
											/>
											<Label
												htmlFor={`${id}-col-${i}`}
												className="flex flex-1 items-center gap-2 font-normal text-xs cursor-pointer min-w-0"
											>
												<span className="truncate min-w-0">{label}</span>
											</Label>
										</button>
									))}
								</div>
							</div>
						</PopoverContent>
					</Popover>
				</div>

				{/* Bulk Delete Button */}
				{selectedIds.size > 0 && (
					<AlertDialog>
						<AlertDialogTrigger asChild>
							<motion.div
								initial={{ opacity: 0, scale: 0.9 }}
								animate={{ opacity: 1, scale: 1 }}
								exit={{ opacity: 0, scale: 0.9 }}
							>
								<Button
									variant="destructive"
									size="sm"
									className="h-9 gap-2"
								>
									<Trash size={14} />
									Delete
									<span className="flex h-5 w-5 items-center justify-center rounded-full bg-destructive-foreground/20 text-[10px] font-medium">
										{selectedIds.size}
									</span>
								</Button>
							</motion.div>
						</AlertDialogTrigger>
						<AlertDialogContent className="max-w-md">
							<div className="flex flex-col gap-2 sm:flex-row sm:gap-4">
								<div
									className="flex size-10 shrink-0 items-center justify-center rounded-full bg-destructive/10 text-destructive"
									aria-hidden="true"
								>
									<CircleAlert size={18} strokeWidth={2} />
								</div>
								<AlertDialogHeader className="flex-1">
									<AlertDialogTitle>Delete {selectedIds.size} document{selectedIds.size !== 1 ? "s" : ""}?</AlertDialogTitle>
									<AlertDialogDescription>
										This action cannot be undone. This will permanently delete the selected {selectedIds.size === 1 ? "document" : "documents"} from your search space.
									</AlertDialogDescription>
								</AlertDialogHeader>
							</div>
							<AlertDialogFooter>
								<AlertDialogCancel>Cancel</AlertDialogCancel>
								<AlertDialogAction
									onClick={onBulkDelete}
									className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
								>
									Delete
								</AlertDialogAction>
							</AlertDialogFooter>
						</AlertDialogContent>
					</AlertDialog>
				)}
			</div>
		</motion.div>
	);
}
