"use client";

import { formatDistanceToNow } from "date-fns";
import { Calendar, ChevronDown, ChevronUp, FileText, FileX, Link2, Plus, User } from "lucide-react";
import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import React, { useRef, useState, useEffect } from "react";
import { useDocumentUploadDialog } from "@/components/assistant-ui/document-upload-popup";
import { DocumentViewer } from "@/components/document-viewer";
import { JsonMetadataViewer } from "@/components/json-metadata-viewer";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { DocumentTypeChip } from "./DocumentTypeIcon";
import type { ColumnVisibility, Document } from "./types";

export type SortKey = keyof Pick<Document, "title" | "document_type" | "created_at">;

function sortDocuments(docs: Document[], key: SortKey, desc: boolean): Document[] {
	const sorted = [...docs].sort((a, b) => {
		const av = a[key] ?? "";
		const bv = b[key] ?? "";
		if (key === "created_at")
			return new Date(av as string).getTime() - new Date(bv as string).getTime();
		return String(av).localeCompare(String(bv));
	});
	return desc ? sorted.reverse() : sorted;
}

function formatRelativeDate(dateStr: string): string {
	return formatDistanceToNow(new Date(dateStr), { addSuffix: true });
}

function formatAbsoluteDate(dateStr: string): string {
	const date = new Date(dateStr);
	return date.toLocaleString("en-US", {
		year: "numeric",
		month: "long",
		day: "numeric",
		hour: "2-digit",
		minute: "2-digit",
		hour12: false,
	});
}

function TruncatedText({ text, className }: { text: string; className?: string }) {
	const textRef = useRef<HTMLSpanElement>(null);
	const [isTruncated, setIsTruncated] = useState(false);

	useEffect(() => {
		const checkTruncation = () => {
			if (textRef.current) {
				setIsTruncated(textRef.current.scrollWidth > textRef.current.clientWidth);
			}
		};
		checkTruncation();
		window.addEventListener("resize", checkTruncation);
		return () => window.removeEventListener("resize", checkTruncation);
	}, []);

	if (isTruncated) {
		return (
			<Tooltip>
				<TooltipTrigger asChild>
					<span ref={textRef} className={className}>
						{text}
					</span>
				</TooltipTrigger>
				<TooltipContent side="top" className="max-w-xs">
					<p className="break-words">{text}</p>
				</TooltipContent>
			</Tooltip>
		);
	}

	return (
		<span ref={textRef} className={className}>
			{text}
		</span>
	);
}

function SortableHeader({
	children,
	sortKey,
	currentSortKey,
	sortDesc,
	onSort,
	icon,
}: {
	children: React.ReactNode;
	sortKey: SortKey;
	currentSortKey: SortKey;
	sortDesc: boolean;
	onSort: (key: SortKey) => void;
	icon?: React.ReactNode;
}) {
	const isActive = currentSortKey === sortKey;
	return (
		<button
			type="button"
			onClick={() => onSort(sortKey)}
			className="flex items-center gap-1.5 text-left text-sm font-medium text-muted-foreground/70 hover:text-muted-foreground transition-colors group"
		>
			{icon && <span className="opacity-60">{icon}</span>}
			{children}
			<span className={`transition-opacity ${isActive ? "opacity-100" : "opacity-0 group-hover:opacity-50"}`}>
				{isActive && sortDesc ? (
					<ChevronDown size={14} />
				) : (
					<ChevronUp size={14} />
				)}
			</span>
		</button>
	);
}

export function DocumentsTableShell({
	documents,
	loading,
	error,
	onRefresh,
	selectedIds,
	setSelectedIds,
	columnVisibility,
	sortKey,
	sortDesc,
	onSortChange,
}: {
	documents: Document[];
	loading: boolean;
	error: boolean;
	onRefresh: () => Promise<void>;
	selectedIds: Set<number>;
	setSelectedIds: (update: Set<number>) => void;
	columnVisibility: ColumnVisibility;
	sortKey: SortKey;
	sortDesc: boolean;
	onSortChange: (key: SortKey) => void;
}) {
	const t = useTranslations("documents");
	const { openDialog } = useDocumentUploadDialog();

	// State for metadata viewer (opened via Ctrl/Cmd+Click)
	const [metadataDoc, setMetadataDoc] = useState<Document | null>(null);

	const sorted = React.useMemo(
		() => sortDocuments(documents, sortKey, sortDesc),
		[documents, sortKey, sortDesc]
	);

	const allSelectedOnPage = sorted.length > 0 && sorted.every((d) => selectedIds.has(d.id));
	const someSelectedOnPage = sorted.some((d) => selectedIds.has(d.id)) && !allSelectedOnPage;

	const toggleAll = (checked: boolean) => {
		const next = new Set(selectedIds);
		if (checked)
			sorted.forEach((d) => {
				next.add(d.id);
			});
		else
			sorted.forEach((d) => {
				next.delete(d.id);
			});
		setSelectedIds(next);
	};

	const toggleOne = (id: number, checked: boolean) => {
		const next = new Set(selectedIds);
		if (checked) next.add(id);
		else next.delete(id);
		setSelectedIds(next);
	};

	const onSortHeader = (key: SortKey) => onSortChange(key);

	return (
		<motion.div
			className="rounded-lg border border-border/30 bg-background overflow-hidden"
			initial={{ opacity: 0, y: 20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ type: "spring", stiffness: 300, damping: 30, delay: 0.2 }}
		>
			{loading ? (
				<>
					{/* Desktop Skeleton View */}
					<div className="hidden md:flex md:flex-col">
						<Table className="table-fixed w-full">
							<TableHeader>
								<TableRow className="hover:bg-transparent border-b border-border/30">
									<TableHead className="w-8 px-0 text-center border-r border-border/30">
										<div className="flex items-center justify-center h-full">
											<Skeleton className="h-4 w-4 rounded" />
										</div>
									</TableHead>
									<TableHead className="w-[35%] max-w-0 border-r border-border/30">
										<Skeleton className="h-3 w-20" />
									</TableHead>
									{columnVisibility.document_type && (
										<TableHead className="w-44 border-r border-border/30">
											<Skeleton className="h-3 w-14" />
										</TableHead>
									)}
									{columnVisibility.created_by && (
										<TableHead className="w-36 border-r border-border/30">
											<Skeleton className="h-3 w-10" />
										</TableHead>
									)}
									{columnVisibility.created_at && (
										<TableHead className="w-32">
											<Skeleton className="h-3 w-16" />
										</TableHead>
									)}
								</TableRow>
							</TableHeader>
						</Table>
						<div className="h-[50vh] overflow-auto">
							<Table className="table-fixed w-full">
								<TableBody>
									{[65, 80, 45, 72, 55, 88, 40, 60, 50, 75].map((widthPercent, index) => (
										<TableRow
											key={`skeleton-${index}`}
											className="border-b border-border/30 hover:bg-transparent"
										>
											<TableCell className="w-8 px-0 py-2.5 text-center border-r border-border/30">
												<div className="flex items-center justify-center h-full">
													<Skeleton className="h-4 w-4 rounded" />
												</div>
											</TableCell>
											<TableCell className="w-[35%] py-2.5 max-w-0 border-r border-border/30">
												<Skeleton
													className="h-4"
													style={{ width: `${widthPercent}%` }}
												/>
											</TableCell>
											{columnVisibility.document_type && (
												<TableCell className="w-44 py-2.5 border-r border-border/30">
													<Skeleton className="h-5 w-24 rounded" />
												</TableCell>
											)}
											{columnVisibility.created_by && (
												<TableCell className="w-36 py-2.5 truncate border-r border-border/30">
													<Skeleton className="h-4 w-20" />
												</TableCell>
											)}
											{columnVisibility.created_at && (
												<TableCell className="w-32 py-2.5">
													<Skeleton className="h-4 w-20" />
												</TableCell>
											)}
										</TableRow>
									))}
								</TableBody>
							</Table>
						</div>
					</div>
					{/* Mobile Skeleton View */}
					<div className="md:hidden divide-y divide-border/30 h-[50vh] overflow-auto">
						{[70, 85, 55, 78, 62, 90].map((widthPercent, index) => (
							<div key={`skeleton-mobile-${index}`} className="px-4 py-3">
								<div className="flex items-start gap-3">
									<Skeleton className="h-4 w-4 mt-0.5 rounded" />
									<div className="flex-1 min-w-0 space-y-2">
										<Skeleton
											className="h-4"
											style={{ width: `${widthPercent}%` }}
										/>
										<div className="flex flex-wrap items-center gap-2">
											<Skeleton className="h-5 w-20 rounded" />
											{columnVisibility.created_by && (
												<Skeleton className="h-3 w-14" />
											)}
											{columnVisibility.created_at && (
												<Skeleton className="h-3 w-20" />
											)}
										</div>
									</div>
									<Skeleton className="h-7 w-7 rounded" />
								</div>
							</div>
						))}
					</div>
				</>
			) : error ? (
				<div className="flex h-[400px] w-full items-center justify-center">
					<div className="flex flex-col items-center gap-3">
						<p className="text-sm text-destructive">{t("error_loading")}</p>
						<Button variant="outline" size="sm" onClick={() => onRefresh()}>
							{t("retry")}
						</Button>
					</div>
				</div>
			) : sorted.length === 0 ? (
				<div className="flex h-[400px] w-full items-center justify-center">
					<motion.div
						initial={{ opacity: 0, y: 20 }}
						animate={{ opacity: 1, y: 0 }}
						transition={{ duration: 0.4 }}
						className="flex flex-col items-center gap-4 max-w-md px-4 text-center"
					>
						<div className="rounded-full bg-muted/50 p-4">
							<FileX className="h-8 w-8 text-muted-foreground/60" />
						</div>
						<div className="space-y-1.5">
							<h3 className="text-lg font-semibold">{t("no_documents")}</h3>
							<p className="text-sm text-muted-foreground">
								Get started by uploading your first document.
							</p>
						</div>
						<Button onClick={openDialog} className="mt-2">
							<Plus className="mr-2 h-4 w-4" />
							Upload Documents
						</Button>
					</motion.div>
				</div>
			) : (
				<>
					{/* Desktop Table View - Notion Style */}
					<div className="hidden md:flex md:flex-col">
						{/* Fixed Header */}
						<Table className="table-fixed w-full">
							<TableHeader>
								<TableRow className="hover:bg-transparent border-b border-border/30">
									<TableHead className="w-8 px-0 text-center border-r border-border/30">
										<div className="flex items-center justify-center h-full">
											<Checkbox
												checked={allSelectedOnPage || (someSelectedOnPage && "indeterminate")}
												onCheckedChange={(v) => toggleAll(!!v)}
												aria-label="Select all"
												className="border-foreground data-[state=checked]:bg-primary data-[state=checked]:border-primary"
											/>
										</div>
									</TableHead>
									<TableHead className="w-[35%] border-r border-border/30">
										<SortableHeader
											sortKey="title"
											currentSortKey={sortKey}
											sortDesc={sortDesc}
											onSort={onSortHeader}
											icon={<FileText size={14} className="text-muted-foreground" />}
										>
											Document
										</SortableHeader>
									</TableHead>
									{columnVisibility.document_type && (
										<TableHead className="w-44 border-r border-border/30">
											<SortableHeader
												sortKey="document_type"
												currentSortKey={sortKey}
												sortDesc={sortDesc}
												onSort={onSortHeader}
												icon={<Link2 size={14} className="text-muted-foreground" />}
											>
												Source
											</SortableHeader>
										</TableHead>
									)}
									{columnVisibility.created_by && (
										<TableHead className="w-36 border-r border-border/30">
											<span className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground/70">
												<User size={14} className="opacity-60 text-muted-foreground" />
												User
											</span>
										</TableHead>
									)}
									{columnVisibility.created_at && (
										<TableHead className="w-32">
											<SortableHeader
												sortKey="created_at"
												currentSortKey={sortKey}
												sortDesc={sortDesc}
												onSort={onSortHeader}
												icon={<Calendar size={14} className="text-muted-foreground" />}
											>
												Created
											</SortableHeader>
										</TableHead>
									)}
								</TableRow>
							</TableHeader>
						</Table>
						{/* Scrollable Body */}
						<div className="h-[50vh] overflow-auto">
							<Table className="table-fixed w-full">
								<TableBody>
									{sorted.map((doc, index) => {
										const title = doc.title;
										const isSelected = selectedIds.has(doc.id);
										return (
											<motion.tr
												key={doc.id}
												initial={{ opacity: 0 }}
												animate={{
													opacity: 1,
													transition: {
														duration: 0.2,
														delay: index * 0.02,
													},
												}}
												className={`border-b border-border/30 transition-colors ${
													isSelected
														? "bg-primary/5 hover:bg-primary/8"
														: "hover:bg-muted/30"
												}`}
											>
												<TableCell className="w-8 px-0 py-2.5 text-center border-r border-border/30">
													<div className="flex items-center justify-center h-full">
														<Checkbox
															checked={isSelected}
															onCheckedChange={(v) => toggleOne(doc.id, !!v)}
															aria-label="Select row"
															className="border-foreground data-[state=checked]:bg-primary data-[state=checked]:border-primary"
														/>
													</div>
												</TableCell>
												<TableCell className="w-[35%] py-2.5 max-w-0 border-r border-border/30">
													<DocumentViewer
														title={doc.title}
														content={doc.content}
														trigger={
															<button
																type="button"
																className="block w-full text-left text-sm text-foreground hover:text-foreground transition-colors cursor-pointer bg-transparent border-0 p-0 truncate"
																onClick={(e) => {
																	// Ctrl (Win/Linux) or Cmd (Mac) + Click opens metadata
																	if (e.ctrlKey || e.metaKey) {
																		e.preventDefault();
																		e.stopPropagation();
																		setMetadataDoc(doc);
																	}
																}}
																onKeyDown={(e) => {
																	// Ctrl/Cmd + Enter opens metadata
																	if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
																		e.preventDefault();
																		setMetadataDoc(doc);
																	}
																}}
															>
																<TruncatedText text={title} className="truncate block" />
															</button>
														}
													/>
												</TableCell>
												{columnVisibility.document_type && (
													<TableCell className="w-44 py-2.5 border-r border-border/30">
														<DocumentTypeChip type={doc.document_type} />
													</TableCell>
												)}
												{columnVisibility.created_by && (
													<TableCell className="w-36 py-2.5 text-sm text-foreground truncate border-r border-border/30">
														{doc.created_by_name || "—"}
													</TableCell>
												)}
												{columnVisibility.created_at && (
													<TableCell className="w-32 py-2.5 text-sm text-foreground">
														<Tooltip>
															<TooltipTrigger asChild>
																<span className="cursor-default">{formatRelativeDate(doc.created_at)}</span>
															</TooltipTrigger>
															<TooltipContent side="top">
																{formatAbsoluteDate(doc.created_at)}
															</TooltipContent>
														</Tooltip>
													</TableCell>
												)}
											</motion.tr>
										);
									})}
								</TableBody>
							</Table>
						</div>
					</div>

					{/* Mobile Card View - Notion Style */}
					<div className="md:hidden divide-y divide-border/30 h-[50vh] overflow-auto">
						{sorted.map((doc, index) => {
							const isSelected = selectedIds.has(doc.id);
							return (
								<motion.div
									key={doc.id}
									initial={{ opacity: 0 }}
									animate={{ opacity: 1, transition: { delay: index * 0.03 } }}
									className={`px-4 py-3 transition-colors ${
										isSelected ? "bg-primary/5" : "hover:bg-muted/20"
									}`}
								>
									<div className="flex items-center gap-3">
										<Checkbox
											checked={isSelected}
											onCheckedChange={(v) => toggleOne(doc.id, !!v)}
											aria-label="Select row"
											className="border-foreground data-[state=checked]:bg-primary data-[state=checked]:border-primary"
										/>
										<div className="flex-1 min-w-0 space-y-1.5">
											<DocumentViewer
												title={doc.title}
												content={doc.content}
												trigger={
													<button
														type="button"
														className="text-left text-sm text-foreground hover:text-foreground transition-colors cursor-pointer truncate block w-full bg-transparent border-0 p-0"
														onClick={(e) => {
															// Ctrl (Win/Linux) or Cmd (Mac) + Click opens metadata
															if (e.ctrlKey || e.metaKey) {
																e.preventDefault();
																e.stopPropagation();
																setMetadataDoc(doc);
															}
														}}
														onKeyDown={(e) => {
															// Ctrl/Cmd + Enter opens metadata
															if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
																e.preventDefault();
																setMetadataDoc(doc);
															}
														}}
													>
														{doc.title}
													</button>
												}
											/>
											<div className="flex flex-wrap items-center gap-2">
												<DocumentTypeChip type={doc.document_type} />
												{columnVisibility.created_by && doc.created_by_name && (
													<span className="text-xs text-foreground">
														{doc.created_by_name}
													</span>
												)}
												{columnVisibility.created_at && (
													<Tooltip>
														<TooltipTrigger asChild>
															<span className="text-xs text-foreground cursor-default">
																{formatRelativeDate(doc.created_at)}
															</span>
														</TooltipTrigger>
														<TooltipContent side="top">
															{formatAbsoluteDate(doc.created_at)}
														</TooltipContent>
													</Tooltip>
												)}
											</div>
										</div>
									</div>
								</motion.div>
							);
						})}
					</div>
				</>
			)}

			{/* Metadata Viewer - opened via Ctrl/Cmd+Click on document title */}
			<JsonMetadataViewer
				title={metadataDoc?.title ?? ""}
				metadata={metadataDoc?.document_metadata}
				open={!!metadataDoc}
				onOpenChange={(open) => {
					if (!open) setMetadataDoc(null);
				}}
			/>
		</motion.div>
	);
}
