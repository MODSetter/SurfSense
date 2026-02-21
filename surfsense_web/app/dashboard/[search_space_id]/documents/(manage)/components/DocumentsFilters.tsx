"use client";

import { useSetAtom } from "jotai";
import {
	CircleAlert,
	FileType,
	ListFilter,
	Search,
	SlidersHorizontal,
	Trash,
	Upload,
	X,
} from "lucide-react";
import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import React, { useMemo, useRef, useState } from "react";
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
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { getDocumentTypeIcon, getDocumentTypeLabel } from "./DocumentTypeIcon";

export function DocumentsFilters({
	typeCounts: typeCountsRecord,
	selectedIds,
	onSearch,
	searchValue,
	onBulkDelete,
	onToggleType,
	activeTypes,
}: {
	typeCounts: Partial<Record<DocumentTypeEnum, number>>;
	selectedIds: Set<number>;
	onSearch: (v: string) => void;
	searchValue: string;
	onBulkDelete: () => Promise<void>;
	onToggleType: (type: DocumentTypeEnum, checked: boolean) => void;
	activeTypes: DocumentTypeEnum[];
}) {
	const t = useTranslations("documents");
	const id = React.useId();
	const inputRef = useRef<HTMLInputElement>(null);

	// Dialog hooks for action buttons
	const { openDialog: openUploadDialog } = useDocumentUploadDialog();
	const setConnectorDialogOpen = useSetAtom(connectorDialogOpenAtom);

	const [typeSearchQuery, setTypeSearchQuery] = useState("");

	const uniqueTypes = useMemo(() => {
		return Object.keys(typeCountsRecord).sort() as DocumentTypeEnum[];
	}, [typeCountsRecord]);

	const filteredTypes = useMemo(() => {
		if (!typeSearchQuery.trim()) return uniqueTypes;
		const query = typeSearchQuery.toLowerCase();
		return uniqueTypes.filter((type) => getDocumentTypeLabel(type).toLowerCase().includes(query));
	}, [uniqueTypes, typeSearchQuery]);

	const typeCounts = useMemo(() => {
		const map = new Map<string, number>();
		for (const [type, count] of Object.entries(typeCountsRecord)) {
			map.set(type, count);
		}
		return map;
	}, [typeCountsRecord]);

	return (
		<motion.div
			className="flex flex-col gap-4 select-none"
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
						<Upload size={16} />
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
					<div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-muted-foreground">
						<ListFilter size={14} aria-hidden="true" />
					</div>
					<Input
						id={`${id}-input`}
						ref={inputRef}
						className="peer h-9 w-full pl-9 pr-9 text-sm bg-background border-border/60 focus-visible:ring-1 focus-visible:ring-ring/30 select-none focus:select-text"
						value={searchValue}
						onChange={(e) => onSearch(e.target.value)}
						placeholder="Filter by title"
						type="text"
						aria-label={t("filter_placeholder")}
					/>
					{Boolean(searchValue) && (
						<motion.button
							className="absolute inset-y-0 right-0 flex h-full w-9 items-center justify-center rounded-r-md text-muted-foreground hover:text-foreground transition-colors"
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
							<X size={14} strokeWidth={2} aria-hidden="true" />
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
							<div>
								{/* Search input */}
								<div className="p-2 border-b border-border/50">
									<div className="relative">
										<Search className="absolute left-0.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
										<Input
											placeholder="Search types"
											value={typeSearchQuery}
											onChange={(e) => setTypeSearchQuery(e.target.value)}
											className="h-6 pl-6 text-sm bg-transparent border-0 focus-visible:ring-0"
										/>
									</div>
								</div>

								<div className="max-h-[300px] overflow-y-auto overflow-x-hidden py-1.5 px-1.5">
									{filteredTypes.length === 0 ? (
										<div className="py-6 text-center text-sm text-muted-foreground">
											No types found
										</div>
									) : (
										filteredTypes.map((value: DocumentTypeEnum, i) => (
											<div
												key={value}
												role="button"
												tabIndex={0}
												className="flex w-full items-center gap-2.5 py-2 px-3 rounded-md hover:bg-muted/50 transition-colors cursor-pointer text-left"
												onClick={() => onToggleType(value, !activeTypes.includes(value))}
												onKeyDown={(e) => {
													if (e.key === "Enter" || e.key === " ") {
														e.preventDefault();
														onToggleType(value, !activeTypes.includes(value));
													}
												}}
											>
												{/* Icon */}
												<div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-muted/50 text-foreground/80">
													{getDocumentTypeIcon(value, "h-4 w-4")}
												</div>
												{/* Text content */}
												<div className="flex flex-col min-w-0 flex-1 gap-0.5">
													<span className="text-[13px] font-medium text-foreground truncate leading-tight">
														{getDocumentTypeLabel(value)}
													</span>
													<span className="text-[11px] text-muted-foreground leading-tight">
														{typeCounts.get(value)} document
														{(typeCounts.get(value) ?? 0) !== 1 ? "s" : ""}
													</span>
												</div>
												{/* Checkbox */}
												<Checkbox
													id={`${id}-${i}`}
													checked={activeTypes.includes(value)}
													onCheckedChange={(checked: boolean) => onToggleType(value, !!checked)}
													className="h-4 w-4 shrink-0 rounded border-muted-foreground/30 data-[state=checked]:bg-primary data-[state=checked]:border-primary"
												/>
											</div>
										))
									)}
								</div>
								{activeTypes.length > 0 && (
									<div className="px-3 pt-1.5 pb-1.5 border-t border-border/50">
										<Button
											variant="ghost"
											size="sm"
											className="w-full h-7 text-[11px] text-muted-foreground hover:text-foreground"
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

					{/* Bulk Delete Button */}
					{selectedIds.size > 0 && (
						<AlertDialog>
							<AlertDialogTrigger asChild>
								<motion.div
									initial={{ opacity: 0, scale: 0.9 }}
									animate={{ opacity: 1, scale: 1 }}
									exit={{ opacity: 0, scale: 0.9 }}
								>
									{/* Mobile: icon with count */}
									<Button variant="destructive" size="sm" className="h-9 gap-1.5 px-2.5 md:hidden">
										<Trash size={14} />
										<span className="flex h-5 w-5 items-center justify-center rounded-full bg-destructive-foreground/20 text-[10px] font-medium">
											{selectedIds.size}
										</span>
									</Button>
									{/* Desktop: full button */}
									<Button variant="destructive" size="sm" className="h-9 gap-2 hidden md:flex">
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
										<AlertDialogTitle>
											Delete {selectedIds.size} document{selectedIds.size !== 1 ? "s" : ""}?
										</AlertDialogTitle>
										<AlertDialogDescription>
											This action cannot be undone. This will permanently delete the selected{" "}
											{selectedIds.size === 1 ? "document" : "documents"} from your search space.
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
			</div>
		</motion.div>
	);
}
