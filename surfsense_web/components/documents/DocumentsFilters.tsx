"use client";

import { IconBrandGithub } from "@tabler/icons-react";
import { FolderPlus, ListFilter, Search, TriangleAlert, Upload, X } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import React, { useCallback, useMemo, useRef, useState } from "react";
import { useDocumentUploadDialog } from "@/components/assistant-ui/document-upload-popup";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Drawer,
	DrawerContent,
	DrawerHandle,
	DrawerHeader,
	DrawerTitle,
	DrawerTrigger,
} from "@/components/ui/drawer";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { useIsMobile } from "@/hooks/use-mobile";
import { getDocumentTypeLabel } from "@/lib/documents/document-type-labels";
import { cn } from "@/lib/utils";
import { getDocumentTypeIcon } from "./DocumentTypeIcon";

function DocumentTypeFilterList({
	typeCountsRecord,
	activeTypes,
	onToggleType,
	mobile = false,
}: {
	typeCountsRecord: Partial<Record<DocumentTypeEnum, number>>;
	activeTypes: DocumentTypeEnum[];
	onToggleType: (type: DocumentTypeEnum, checked: boolean) => void;
	mobile?: boolean;
}) {
	const id = React.useId();
	const [search, setSearch] = useState("");
	const [scrollPos, setScrollPos] = useState<"top" | "middle" | "bottom">("top");
	const typeCounts = useMemo(() => new Map(Object.entries(typeCountsRecord)), [typeCountsRecord]);
	const filteredTypes = useMemo(() => {
		const types = Object.keys(typeCountsRecord).sort() as DocumentTypeEnum[];
		const query = search.trim().toLowerCase();
		return query
			? types.filter((type) => getDocumentTypeLabel(type).toLowerCase().includes(query))
			: types;
	}, [typeCountsRecord, search]);

	const handleScroll = useCallback((event: React.UIEvent<HTMLDivElement>) => {
		const element = event.currentTarget;
		const atTop = element.scrollTop <= 2;
		const atBottom = element.scrollHeight - element.scrollTop - element.clientHeight <= 2;
		setScrollPos(atTop ? "top" : atBottom ? "bottom" : "middle");
	}, []);

	return (
		<div className={cn("flex min-h-0 flex-col", mobile && "flex-1")}>
			{mobile ? null : (
				<div className="p-2">
					<div className="relative">
						<Search className="absolute left-2 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
						<Input
							aria-label="Search document types"
							placeholder="Search types"
							value={search}
							onChange={(event) => setSearch(event.target.value)}
							className="h-7 border-0 bg-transparent pl-8 text-sm shadow-none"
						/>
					</div>
				</div>
			)}

			<div
				role="listbox"
				aria-label="Document types"
				aria-multiselectable="true"
				className={cn(
					"overflow-y-auto overflow-x-hidden px-1.5 py-1.5",
					mobile ? "min-h-0 flex-1 px-3 pb-6" : "max-h-[300px]"
				)}
				onScroll={handleScroll}
				style={{
					maskImage: `linear-gradient(to bottom, ${scrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${scrollPos === "bottom" ? "black" : "transparent"})`,
					WebkitMaskImage: `linear-gradient(to bottom, ${scrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${scrollPos === "bottom" ? "black" : "transparent"})`,
				}}
			>
				{filteredTypes.length === 0 ? (
					<div className="py-8 text-center text-sm text-muted-foreground">No types found</div>
				) : (
					filteredTypes.map((value) => {
						const checked = activeTypes.includes(value);
						const count = typeCounts.get(value) ?? 0;
						return (
							<div
								role="option"
								aria-selected={checked}
								tabIndex={0}
								key={value}
								className={cn(
									"flex w-full cursor-pointer items-center gap-2.5 rounded-md px-3 text-left transition-colors hover:bg-accent hover:text-accent-foreground",
									mobile ? "min-h-12 py-2.5" : "py-2"
								)}
								onClick={() => onToggleType(value, !checked)}
								onKeyDown={(event) => {
									if (event.key === "Enter" || event.key === " ") {
										event.preventDefault();
										onToggleType(value, !checked);
									}
								}}
							>
								<div className="flex size-7 shrink-0 items-center justify-center rounded-md bg-muted/50 text-foreground/80">
									{getDocumentTypeIcon(value, "size-4")}
								</div>
								<div className="flex min-w-0 flex-1 flex-col gap-0.5">
									<span className="truncate text-[13px] font-medium leading-tight text-foreground">
										{getDocumentTypeLabel(value)}
									</span>
									<span className="text-[11px] leading-tight text-muted-foreground">
										{count} document{count !== 1 ? "s" : ""}
									</span>
								</div>
								<Checkbox
									id={`${id}-${value}`}
									checked={checked}
									aria-label={`Filter by ${getDocumentTypeLabel(value)}`}
									onCheckedChange={(nextChecked) => onToggleType(value, nextChecked === true)}
									onClick={(event) => event.stopPropagation()}
									className="size-4 shrink-0 rounded border-muted-foreground/30 data-[state=checked]:border-primary data-[state=checked]:bg-primary"
								/>
							</div>
						);
					})
				)}
			</div>
		</div>
	);
}

export function DocumentsFilters({
	typeCounts: typeCountsRecord,
	onSearch,
	searchValue,
	onToggleType,
	activeTypes,
	onCreateFolder,
	onUploadClick,
	isUploading = false,
	connectRepoHref,
	repoConnected = false,
	syncNeedsAttention = false,
}: {
	typeCounts: Partial<Record<DocumentTypeEnum, number>>;
	onSearch: (v: string) => void;
	searchValue: string;
	onToggleType: (type: DocumentTypeEnum, checked: boolean) => void;
	activeTypes: DocumentTypeEnum[];
	onCreateFolder?: () => void;
	onUploadClick?: () => void;
	isUploading?: boolean;
	connectRepoHref?: string;
	repoConnected?: boolean;
	syncNeedsAttention?: boolean;
}) {
	const t = useTranslations("documents");
	const id = React.useId();
	const inputRef = useRef<HTMLInputElement>(null);
	const isMobile = useIsMobile();

	const { openDialog: openUploadDialog } = useDocumentUploadDialog();
	const handleUpload = onUploadClick ?? openUploadDialog;
	const [filterOpen, setFilterOpen] = useState(false);
	const filterTrigger = (
		<ToggleGroupItem
			value="filter"
			aria-label="Filter"
			className="relative size-8 shrink-0 overflow-visible border-0 bg-muted text-muted-foreground transition-colors before:absolute before:left-0 before:top-1/2 before:h-4 before:w-px before:-translate-y-1/2 before:bg-border/60 before:content-[''] hover:bg-accent hover:text-accent-foreground dark:before:bg-white/10"
		>
			<ListFilter size={13} />
			{activeTypes.length > 0 ? (
				<span className="absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full bg-primary text-[9px] font-medium text-primary-foreground">
					{activeTypes.length}
				</span>
			) : null}
		</ToggleGroupItem>
	);

	return (
		<div className="flex select-none flex-col gap-2">
			{/* Search Input */}
			<div className="relative w-full">
				<div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-muted-foreground">
					<Search size={16} aria-hidden="true" />
				</div>
				<Input
					id={`${id}-input`}
					ref={inputRef}
					className="h-9 w-full select-none border-0 bg-muted pl-9 pr-7 text-sm shadow-none focus:select-text [&::-webkit-search-cancel-button]:hidden"
					value={searchValue}
					onChange={(e) => onSearch(e.target.value)}
					onKeyDown={(event) => {
						if (event.key === "Escape" && searchValue) {
							event.preventDefault();
							onSearch("");
						}
					}}
					placeholder={t("search_documents")}
					type="search"
					autoComplete="off"
					enterKeyHint="search"
					spellCheck={false}
					aria-label={t("search_documents")}
				/>
				{Boolean(searchValue) && (
					<Button
						type="button"
						variant="ghost"
						size="icon"
						className="absolute right-2 top-1/2 h-5 w-5 -translate-y-1/2 rounded-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
						aria-label="Clear filter"
						onClick={() => {
							onSearch("");
							inputRef.current?.focus();
						}}
					>
						<X size={14} strokeWidth={2} aria-hidden="true" />
					</Button>
				)}
			</div>

			<div className="flex w-full flex-wrap items-center gap-2">
				{/* Upload Button */}
				<Button
					data-joyride="upload-button"
					onClick={handleUpload}
					disabled={isUploading}
					variant="outline"
					size="sm"
					className="h-8 min-w-0 basis-36 flex-1 gap-1.5 border-0 bg-white text-gray-700 shadow-none hover:bg-accent hover:text-accent-foreground dark:bg-white dark:text-gray-800"
				>
					{isUploading ? <Spinner size="xs" /> : <Upload size={13} />}
					<span className="truncate">{isUploading ? t("uploading") : t("upload_files")}</span>
				</Button>
				{connectRepoHref ? (
					<Tooltip>
						<TooltipTrigger asChild>
							<Button
								asChild
								variant="outline"
								size="sm"
								className="relative h-8 min-w-0 basis-36 flex-1 gap-1.5 overflow-visible border-0 bg-white text-gray-700 shadow-none hover:bg-accent hover:text-accent-foreground dark:bg-white dark:text-gray-800"
							>
								<Link href={connectRepoHref}>
									<IconBrandGithub size={13} className="shrink-0" />
									<span className="truncate">
										{repoConnected ? t("manage_repo") : t("connect_repo")}
									</span>
									{syncNeedsAttention ? (
										<span
											role="img"
											aria-label={t("connect_repo_attention")}
											className="absolute -right-1.5 -top-1.5 flex items-center justify-center  rounded-full bg-yellow-400 text-red-400"
										>
											<TriangleAlert size={10} className="shrink-0 text-red-400" aria-hidden />
										</span>
									) : null}
								</Link>
							</Button>
						</TooltipTrigger>
						{syncNeedsAttention ? (
							<TooltipContent>{t("connect_repo_attention")}</TooltipContent>
						) : null}
					</Tooltip>
				) : null}

				{/* New Folder + Filter Toggle Group */}
				<ToggleGroup type="multiple" value={[]} className="shrink-0 overflow-visible">
					{onCreateFolder && (
						<Tooltip>
							<TooltipTrigger asChild>
								<ToggleGroupItem
									value="folder"
									className="h-8 w-8 shrink-0 border-0 bg-muted text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
									onClick={(e) => {
										e.preventDefault();
										onCreateFolder();
									}}
								>
									<FolderPlus size={13} />
								</ToggleGroupItem>
							</TooltipTrigger>
							<TooltipContent>New folder</TooltipContent>
						</Tooltip>
					)}

					{isMobile ? (
						<Drawer open={filterOpen} onOpenChange={setFilterOpen} shouldScaleBackground={false}>
							<DrawerTrigger asChild>{filterTrigger}</DrawerTrigger>
							<DrawerContent className="h-[70vh] max-h-[80vh] overflow-hidden rounded-t-2xl border bg-popover text-popover-foreground">
								<DrawerHandle className="mt-3 h-1.5 w-10" />
								<DrawerHeader className="px-4 pb-3 pt-2 text-center">
									<DrawerTitle className="text-base">Filter</DrawerTitle>
								</DrawerHeader>
								<DocumentTypeFilterList
									typeCountsRecord={typeCountsRecord}
									activeTypes={activeTypes}
									onToggleType={onToggleType}
									mobile
								/>
							</DrawerContent>
						</Drawer>
					) : (
						<Popover open={filterOpen} onOpenChange={setFilterOpen}>
							<Tooltip>
								<TooltipTrigger asChild>
									<PopoverTrigger asChild>{filterTrigger}</PopoverTrigger>
								</TooltipTrigger>
								<TooltipContent>Filter</TooltipContent>
							</Tooltip>
							<PopoverContent className="w-52 overflow-hidden p-0" align="start">
								<DocumentTypeFilterList
									typeCountsRecord={typeCountsRecord}
									activeTypes={activeTypes}
									onToggleType={onToggleType}
								/>
							</PopoverContent>
						</Popover>
					)}
				</ToggleGroup>
			</div>
		</div>
	);
}
