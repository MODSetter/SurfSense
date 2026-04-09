"use client";

import { Download, FolderPlus, ListFilter, Search, Upload, X } from "lucide-react";
import { useTranslations } from "next-intl";
import React, { useCallback, useMemo, useRef, useState } from "react";
import { useDocumentUploadDialog } from "@/components/assistant-ui/document-upload-popup";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { getDocumentTypeIcon, getDocumentTypeLabel } from "./DocumentTypeIcon";

export function DocumentsFilters({
	typeCounts: typeCountsRecord,
	onSearch,
	searchValue,
	onToggleType,
	activeTypes,
	onCreateFolder,
	onExportKB,
}: {
	typeCounts: Partial<Record<DocumentTypeEnum, number>>;
	onSearch: (v: string) => void;
	searchValue: string;
	onToggleType: (type: DocumentTypeEnum, checked: boolean) => void;
	activeTypes: DocumentTypeEnum[];
	onCreateFolder?: () => void;
	onExportKB?: () => void;
}) {
	const t = useTranslations("documents");
	const id = React.useId();
	const inputRef = useRef<HTMLInputElement>(null);

	const { openDialog: openUploadDialog } = useDocumentUploadDialog();

	const [typeSearchQuery, setTypeSearchQuery] = useState("");
	const [scrollPos, setScrollPos] = useState<"top" | "middle" | "bottom">("top");
	const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
		const el = e.currentTarget;
		const atTop = el.scrollTop <= 2;
		const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= 2;
		setScrollPos(atTop ? "top" : atBottom ? "bottom" : "middle");
	}, []);

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
		<div className="flex select-none">
			<div className="flex items-center gap-2 w-full">
				{/* Filter + New Folder Toggle Group */}
				<ToggleGroup type="multiple" variant="outline" value={[]} className="overflow-visible">
					{onCreateFolder && (
						<Tooltip>
							<TooltipTrigger asChild>
								<ToggleGroupItem
									value="folder"
									className="h-9 w-9 shrink-0 border-sidebar-border text-sidebar-foreground/60 hover:text-sidebar-foreground hover:border-sidebar-border bg-sidebar"
									onClick={(e) => {
										e.preventDefault();
										onCreateFolder();
									}}
								>
									<FolderPlus size={14} />
								</ToggleGroupItem>
							</TooltipTrigger>
							<TooltipContent>New folder</TooltipContent>
						</Tooltip>
					)}

					{onExportKB && (
						<Tooltip>
							<TooltipTrigger asChild>
								<ToggleGroupItem
									value="export"
									className="h-9 w-9 shrink-0 border-sidebar-border text-sidebar-foreground/60 hover:text-sidebar-foreground hover:border-sidebar-border bg-sidebar"
									onClick={(e) => {
										e.preventDefault();
										onExportKB();
									}}
								>
									<Download size={14} />
								</ToggleGroupItem>
							</TooltipTrigger>
							<TooltipContent>Export knowledge base</TooltipContent>
						</Tooltip>
					)}

					<Popover>
						<Tooltip>
							<TooltipTrigger asChild>
								<PopoverTrigger asChild>
									<ToggleGroupItem
										value="filter"
										className="relative h-9 w-9 shrink-0 border-sidebar-border text-sidebar-foreground/60 hover:text-sidebar-foreground hover:border-sidebar-border bg-sidebar overflow-visible"
									>
										<ListFilter size={14} />
										{activeTypes.length > 0 && (
											<span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-sidebar-border text-[9px] font-medium text-sidebar-foreground">
												{activeTypes.length}
											</span>
										)}
									</ToggleGroupItem>
								</PopoverTrigger>
							</TooltipTrigger>
							<TooltipContent>Filter by type</TooltipContent>
						</Tooltip>
						<PopoverContent className="w-56 md:w-52 !p-0 overflow-hidden" align="start">
							<div>
								<div className="p-2">
									<div className="relative">
										<Search className="absolute left-0.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
										<Input
											placeholder="Search types"
											value={typeSearchQuery}
											onChange={(e) => setTypeSearchQuery(e.target.value)}
											className="h-6 pl-6 text-sm bg-transparent border-0 shadow-none"
										/>
									</div>
								</div>

								<div
									className="max-h-[300px] overflow-y-auto overflow-x-hidden py-1.5 px-1.5"
									onScroll={handleScroll}
									style={{
										maskImage: `linear-gradient(to bottom, ${scrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${scrollPos === "bottom" ? "black" : "transparent"})`,
										WebkitMaskImage: `linear-gradient(to bottom, ${scrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${scrollPos === "bottom" ? "black" : "transparent"})`,
									}}
								>
									{filteredTypes.length === 0 ? (
										<div className="py-6 text-center text-sm text-muted-foreground">
											No types found
										</div>
									) : (
										filteredTypes.map((value: DocumentTypeEnum, i) => (
											<div
												role="option"
												aria-selected={activeTypes.includes(value)}
												tabIndex={0}
												key={value}
												className="flex w-full items-center gap-2.5 py-2 px-3 rounded-md hover:bg-neutral-200 dark:hover:bg-neutral-700 transition-colors cursor-pointer text-left"
												onClick={() => onToggleType(value, !activeTypes.includes(value))}
												onKeyDown={(e) => {
													if (e.key === "Enter" || e.key === " ") {
														e.preventDefault();
														onToggleType(value, !activeTypes.includes(value));
													}
												}}
											>
												<div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-muted/50 text-foreground/80">
													{getDocumentTypeIcon(value, "h-4 w-4")}
												</div>
												<div className="flex flex-col min-w-0 flex-1 gap-0.5">
													<span className="text-[13px] font-medium text-foreground truncate leading-tight">
														{getDocumentTypeLabel(value)}
													</span>
													<span className="text-[11px] text-muted-foreground leading-tight">
														{typeCounts.get(value)} document
														{(typeCounts.get(value) ?? 0) !== 1 ? "s" : ""}
													</span>
												</div>
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
							</div>
						</PopoverContent>
					</Popover>
				</ToggleGroup>

				{/* Search Input */}
				<div className="relative flex-1 min-w-0">
					<div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-muted-foreground">
						<Search size={14} aria-hidden="true" />
					</div>
					<Input
						id={`${id}-input`}
						ref={inputRef}
						className="peer h-9 w-full pl-9 pr-9 text-sm bg-sidebar border-border/60 select-none focus:select-text"
						value={searchValue}
						onChange={(e) => onSearch(e.target.value)}
						placeholder="Search docs"
						type="text"
						aria-label={t("filter_placeholder")}
					/>
					{Boolean(searchValue) && (
						<button
							type="button"
							className="absolute inset-y-0 right-0 flex h-full w-9 items-center justify-center rounded-r-md text-muted-foreground hover:text-foreground transition-colors"
							aria-label="Clear filter"
							onClick={() => {
								onSearch("");
								inputRef.current?.focus();
							}}
						>
							<X size={14} strokeWidth={2} aria-hidden="true" />
						</button>
					)}
				</div>

				{/* Upload Button */}
				<Button
					data-joyride="upload-button"
					onClick={openUploadDialog}
					variant="outline"
					size="sm"
					className="h-9 shrink-0 gap-1.5 bg-white text-gray-700 border-white hover:bg-gray-50 dark:bg-white dark:text-gray-800 dark:hover:bg-gray-100"
				>
					<Upload size={14} />
					<span>Upload</span>
				</Button>
			</div>
		</div>
	);
}
