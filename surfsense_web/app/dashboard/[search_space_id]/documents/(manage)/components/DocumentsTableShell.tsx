"use client";

import {
	AlertCircle,
	CheckCircle2,
	ChevronDown,
	ChevronUp,
	Clock,
	Eye,
	FileText,
	FileX,
	Network,
	PenLine,
	Plus,
	Trash2,
} from "lucide-react";
import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useDocumentUploadDialog } from "@/components/assistant-ui/document-upload-popup";
import { MarkdownViewer } from "@/components/markdown-viewer";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	ContextMenu,
	ContextMenuContent,
	ContextMenuItem,
	ContextMenuSeparator,
	ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { getDocumentTypeIcon, getDocumentTypeLabel } from "./DocumentTypeIcon";
import type { ColumnVisibility, Document, DocumentStatus } from "./types";

const EDITABLE_DOCUMENT_TYPES = ["FILE", "NOTE"] as const;
const NON_DELETABLE_DOCUMENT_TYPES = ["SURFSENSE_DOCS"] as const;

function StatusIndicator({ status }: { status?: DocumentStatus }) {
	const state = status?.state ?? "ready";

	switch (state) {
		case "pending":
			return (
				<Tooltip>
					<TooltipTrigger asChild>
						<div className="flex items-center justify-center">
							<Clock className="h-5 w-5 text-muted-foreground/60" />
						</div>
					</TooltipTrigger>
					<TooltipContent side="top">Pending - waiting to be synced</TooltipContent>
				</Tooltip>
			);
		case "processing":
			return (
				<Tooltip>
					<TooltipTrigger asChild>
						<div className="flex items-center justify-center">
							<Spinner size="sm" className="text-primary" />
						</div>
					</TooltipTrigger>
					<TooltipContent side="top">Syncing</TooltipContent>
				</Tooltip>
			);
		case "failed":
			return (
				<Tooltip>
					<TooltipTrigger asChild>
						<div className="flex items-center justify-center">
							<AlertCircle className="h-5 w-5 text-destructive" />
						</div>
					</TooltipTrigger>
					<TooltipContent side="top" className="max-w-xs">
						{status?.reason || "Processing failed"}
					</TooltipContent>
				</Tooltip>
			);
		case "ready":
			return (
				<Tooltip>
					<TooltipTrigger asChild>
						<div className="flex items-center justify-center">
							<CheckCircle2 className="h-5 w-5 text-muted-foreground/60" />
						</div>
					</TooltipTrigger>
					<TooltipContent side="top">Ready</TooltipContent>
				</Tooltip>
			);
	}
}

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

function DocumentNameTooltip({
	doc,
	className,
}: {
	doc: Document;
	className?: string;
}) {
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

	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<span ref={textRef} className={className}>
					{doc.title}
				</span>
			</TooltipTrigger>
			<TooltipContent side="top" align="start" className="max-w-sm">
				<div className="space-y-1 text-xs">
					{isTruncated && (
						<p className="font-medium text-sm break-words">{doc.title}</p>
					)}
					<p>
						<span className="text-muted-foreground">Owner:</span>{" "}
						{doc.created_by_name || doc.created_by_email || "—"}
					</p>
					<p>
						<span className="text-muted-foreground">Created:</span>{" "}
						{formatAbsoluteDate(doc.created_at)}
					</p>
				</div>
			</TooltipContent>
		</Tooltip>
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
			<span
				className={`transition-opacity ${isActive ? "opacity-100" : "opacity-0 group-hover:opacity-50"}`}
			>
				{isActive && sortDesc ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
			</span>
		</button>
	);
}

function RowContextMenu({
	doc,
	children,
	onPreview,
	onDelete,
	searchSpaceId,
}: {
	doc: Document;
	children: React.ReactNode;
	onPreview: (doc: Document) => void;
	onDelete: (doc: Document) => void;
	searchSpaceId: string;
}) {
	const router = useRouter();

	const isEditable = EDITABLE_DOCUMENT_TYPES.includes(
		doc.document_type as (typeof EDITABLE_DOCUMENT_TYPES)[number]
	);
	const isBeingProcessed =
		doc.status?.state === "pending" || doc.status?.state === "processing";
	const isFileFailed = doc.document_type === "FILE" && doc.status?.state === "failed";
	const shouldShowDelete = !NON_DELETABLE_DOCUMENT_TYPES.includes(
		doc.document_type as (typeof NON_DELETABLE_DOCUMENT_TYPES)[number]
	);
	const isEditDisabled = isBeingProcessed || isFileFailed;
	const isDeleteDisabled = isBeingProcessed;

	return (
		<ContextMenu>
			<ContextMenuTrigger asChild>{children}</ContextMenuTrigger>
			<ContextMenuContent className="w-48">
				<ContextMenuItem onClick={() => onPreview(doc)}>
					<Eye className="h-4 w-4" />
					Preview
				</ContextMenuItem>
				{isEditable && (
					<ContextMenuItem
						onClick={() =>
							!isEditDisabled &&
							router.push(`/dashboard/${searchSpaceId}/editor/${doc.id}`)
						}
						disabled={isEditDisabled}
					>
						<PenLine className="h-4 w-4" />
						Edit
					</ContextMenuItem>
				)}
				{shouldShowDelete && (
					<>
						<ContextMenuSeparator />
						<ContextMenuItem
							variant="destructive"
							onClick={() => !isDeleteDisabled && onDelete(doc)}
							disabled={isDeleteDisabled}
						>
							<Trash2 className="h-4 w-4" />
							Delete
						</ContextMenuItem>
					</>
				)}
			</ContextMenuContent>
		</ContextMenu>
	);
}

export function DocumentsTableShell({
	documents,
	loading,
	error,
	selectedIds,
	setSelectedIds,
	columnVisibility: _columnVisibility,
	sortKey,
	sortDesc,
	onSortChange,
	deleteDocument,
	searchSpaceId,
	hasMore = false,
	loadingMore = false,
	onLoadMore,
	isSearchMode = false,
}: {
	documents: Document[];
	loading: boolean;
	error: boolean;
	selectedIds: Set<number>;
	setSelectedIds: (update: Set<number>) => void;
	columnVisibility: ColumnVisibility;
	sortKey: SortKey;
	sortDesc: boolean;
	onSortChange: (key: SortKey) => void;
	deleteDocument: (id: number) => Promise<boolean>;
	searchSpaceId: string;
	hasMore?: boolean;
	loadingMore?: boolean;
	onLoadMore?: () => void;
	isSearchMode?: boolean;
}) {
	const t = useTranslations("documents");
	const { openDialog } = useDocumentUploadDialog();

	const [viewingDoc, setViewingDoc] = useState<Document | null>(null);
	const [viewingContent, setViewingContent] = useState<string>("");
	const [viewingLoading, setViewingLoading] = useState(false);

	const [deleteDoc, setDeleteDoc] = useState<Document | null>(null);
	const [isDeleting, setIsDeleting] = useState(false);

	const desktopSentinelRef = useRef<HTMLDivElement>(null);
	const mobileSentinelRef = useRef<HTMLDivElement>(null);
	const desktopScrollRef = useRef<HTMLDivElement>(null);
	const mobileScrollRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		if (!onLoadMore || !hasMore || loadingMore) return;

		const observers: IntersectionObserver[] = [];

		const observe = (root: HTMLElement | null, sentinel: HTMLElement | null) => {
			if (!root || !sentinel) return;
			const observer = new IntersectionObserver(
				(entries) => {
					if (entries.some((e) => e.isIntersecting)) onLoadMore();
				},
				{ root, rootMargin: "150px", threshold: 0 }
			);
			observer.observe(sentinel);
			observers.push(observer);
		};

		observe(desktopScrollRef.current, desktopSentinelRef.current);
		observe(mobileScrollRef.current, mobileSentinelRef.current);

		return () => { for (const o of observers) o.disconnect(); };
	}, [onLoadMore, hasMore, loadingMore]);

	const handleViewDocument = useCallback(async (doc: Document) => {
		setViewingDoc(doc);
		if (doc.content) {
			setViewingContent(doc.content);
			return;
		}
		setViewingLoading(true);
		try {
			const fullDoc = await documentsApiService.getDocument({ id: doc.id });
			setViewingContent(fullDoc.content);
		} catch (err) {
			console.error("[DocumentsTableShell] Failed to fetch document content:", err);
			setViewingContent("Failed to load document content.");
		} finally {
			setViewingLoading(false);
		}
	}, []);

	const handleCloseViewer = useCallback(() => {
		setViewingDoc(null);
		setViewingContent("");
		setViewingLoading(false);
	}, []);

	const handleDeleteFromMenu = useCallback(
		async () => {
			if (!deleteDoc) return;
			setIsDeleting(true);
			try {
				const ok = await deleteDocument(deleteDoc.id);
				if (!ok) toast.error("Failed to delete document");
			} catch (error: unknown) {
				console.error("Error deleting document:", error);
				const status =
					(error as { response?: { status?: number } })?.response?.status ??
					(error as { status?: number })?.status;
				if (status === 409) {
					toast.error("Document is now being processed. Please try again later.");
				} else {
					toast.error("Failed to delete document");
				}
			} finally {
				setIsDeleting(false);
				setDeleteDoc(null);
			}
		},
		[deleteDoc, deleteDocument]
	);

	const sorted = React.useMemo(
		() => sortDocuments(documents, sortKey, sortDesc),
		[documents, sortKey, sortDesc]
	);

	const isSelectable = (doc: Document) => {
		const state = doc.status?.state;
		return state !== "pending" && state !== "processing";
	};

	const selectableDocs = sorted.filter(isSelectable);
	const allSelectedOnPage =
		selectableDocs.length > 0 && selectableDocs.every((d) => selectedIds.has(d.id));
	const someSelectedOnPage =
		selectableDocs.some((d) => selectedIds.has(d.id)) && !allSelectedOnPage;

	const toggleAll = (checked: boolean) => {
		const next = new Set(selectedIds);
		if (checked)
			selectableDocs.forEach((d) => {
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
			className="bg-background overflow-hidden select-none border-t border-border/50 flex-1 flex flex-col min-h-0"
			initial={{ opacity: 0, y: 20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ type: "spring", stiffness: 300, damping: 30, delay: 0.2 }}
		>
			{loading ? (
				<>
					{/* Desktop Skeleton */}
					<div className="hidden md:flex md:flex-col flex-1 min-h-0">
						<Table className="table-fixed w-full">
							<TableHeader>
								<TableRow className="hover:bg-transparent border-b border-border/50">
									<TableHead className="w-10 pl-3 pr-0 text-center h-8">
										<div className="flex items-center justify-center h-full">
											<Skeleton className="h-4 w-4 rounded" />
										</div>
									</TableHead>
									<TableHead className="h-8 px-2">
										<Skeleton className="h-3 w-20" />
									</TableHead>
									<TableHead className="w-10 text-center h-8 px-0">
										<Skeleton className="h-3 w-4 mx-auto" />
									</TableHead>
									<TableHead className="w-12 text-center h-8 pl-0 pr-3">
										<Skeleton className="h-3 w-8 mx-auto" />
									</TableHead>
								</TableRow>
							</TableHeader>
						</Table>
						<div className="flex-1 overflow-auto">
							<Table className="table-fixed w-full">
								<TableBody>
									{[65, 80, 45, 72, 55, 88, 40, 60, 50, 75].map((widthPercent) => (
										<TableRow
											key={`skeleton-${widthPercent}`}
											className="border-b border-border/50 hover:bg-transparent"
										>
											<TableCell className="w-10 pl-3 pr-0 py-1.5 text-center">
												<div className="flex items-center justify-center h-full">
													<Skeleton className="h-4 w-4 rounded" />
												</div>
											</TableCell>
											<TableCell className="px-2 py-1.5 max-w-0">
												<Skeleton className="h-4" style={{ width: `${widthPercent}%` }} />
											</TableCell>
											<TableCell className="w-10 px-0 py-1.5 text-center">
												<Skeleton className="h-4 w-4 mx-auto rounded" />
											</TableCell>
											<TableCell className="w-12 pl-0 pr-3 py-1.5 text-center">
												<Skeleton className="h-5 w-5 mx-auto rounded-full" />
											</TableCell>
										</TableRow>
									))}
								</TableBody>
							</Table>
						</div>
					</div>
					{/* Mobile Skeleton */}
					<div className="md:hidden divide-y divide-border/50 flex-1 overflow-auto">
						{[70, 85, 55, 78, 62, 90].map((widthPercent) => (
							<div key={`skeleton-mobile-${widthPercent}`} className="px-3 py-2">
								<div className="flex items-center gap-3">
									<Skeleton className="h-4 w-4 rounded shrink-0" />
									<div className="flex-1 min-w-0">
										<Skeleton className="h-4" style={{ width: `${widthPercent}%` }} />
									</div>
									<div className="flex items-center gap-2">
										<Skeleton className="h-4 w-4 rounded shrink-0" />
										<Skeleton className="h-5 w-5 rounded-full shrink-0" />
									</div>
								</div>
							</div>
						))}
					</div>
				</>
			) : error ? (
				<div className="flex flex-1 w-full items-center justify-center">
					<div className="flex flex-col items-center gap-3">
						<AlertCircle className="h-8 w-8 text-destructive" />
						<p className="text-sm text-destructive">{t("error_loading")}</p>
					</div>
				</div>
			) : sorted.length === 0 ? (
				<div className="flex flex-1 w-full items-center justify-center">
					<motion.div
						initial={{ opacity: 0, y: 20 }}
						animate={{ opacity: 1, y: 0 }}
						transition={{ duration: 0.4 }}
						className="flex flex-col items-center gap-4 max-w-md px-4 text-center"
					>
						<div className="rounded-full bg-muted/50 p-4">
							<FileX className="h-8 w-8 text-muted-foreground" />
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
					{/* Desktop Table View */}
					<div className="hidden md:flex md:flex-col flex-1 min-h-0">
						<Table className="table-fixed w-full">
							<TableHeader>
								<TableRow className="hover:bg-transparent border-b border-border/50">
									<TableHead className="w-10 pl-3 pr-0 text-center h-8">
										<div className="flex items-center justify-center h-full">
											<Checkbox
												checked={allSelectedOnPage || (someSelectedOnPage && "indeterminate")}
												onCheckedChange={(v) => toggleAll(!!v)}
												aria-label="Select all"
												className="border-foreground data-[state=checked]:bg-primary data-[state=checked]:border-primary"
											/>
										</div>
									</TableHead>
									<TableHead className="h-8 px-2">
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
									<TableHead className="w-10 text-center h-8 px-0">
										<span className="flex items-center justify-center">
											<Network size={14} className="text-muted-foreground/70" />
										</span>
									</TableHead>
									<TableHead className="w-12 text-center h-8 pl-0 pr-3">
										<span className="text-xs font-medium text-muted-foreground/70">
											Status
										</span>
									</TableHead>
								</TableRow>
							</TableHeader>
						</Table>
						<div ref={desktopScrollRef} className="flex-1 overflow-auto">
							<Table className="table-fixed w-full">
								<TableBody>
									{sorted.map((doc, index) => {
										const isSelected = selectedIds.has(doc.id);
										const canSelect = isSelectable(doc);
										return (
											<RowContextMenu
												key={doc.id}
												doc={doc}
												onPreview={handleViewDocument}
												onDelete={setDeleteDoc}
												searchSpaceId={searchSpaceId}
											>
												<motion.tr
													initial={!isSearchMode && index < 20 ? { opacity: 0 } : false}
													animate={{ opacity: 1 }}
													transition={!isSearchMode && index < 20 ? { duration: 0.15, delay: index * 0.02 } : { duration: 0 }}
												className={`border-b border-border/50 transition-colors ${
													isSelected
														? "bg-primary/5 hover:bg-primary/8"
														: "hover:bg-muted/30"
												}`}
											>
												<TableCell className="w-10 pl-3 pr-0 py-1.5 text-center">
													<div className="flex items-center justify-center h-full">
														<Checkbox
															checked={isSelected}
															onCheckedChange={(v) =>
																canSelect && toggleOne(doc.id, !!v)
															}
															disabled={!canSelect}
															aria-label={
																canSelect
																	? "Select row"
																	: "Cannot select while processing"
															}
															className={`border-foreground data-[state=checked]:bg-primary data-[state=checked]:border-primary ${!canSelect ? "opacity-40 cursor-not-allowed" : ""}`}
														/>
													</div>
												</TableCell>
												<TableCell className="px-2 py-1.5 max-w-0">
													<DocumentNameTooltip
														doc={doc}
														className="truncate block text-sm text-foreground cursor-default"
													/>
												</TableCell>
												<TableCell className="w-10 px-0 py-1.5 text-center">
													<Tooltip>
														<TooltipTrigger asChild>
															<span className="flex items-center justify-center">
																{getDocumentTypeIcon(
																	doc.document_type,
																	"h-4 w-4"
																)}
															</span>
														</TooltipTrigger>
														<TooltipContent side="top">
															{getDocumentTypeLabel(doc.document_type)}
														</TooltipContent>
													</Tooltip>
												</TableCell>
												<TableCell className="w-12 pl-0 pr-3 py-1.5 text-center">
													<StatusIndicator status={doc.status} />
												</TableCell>
												</motion.tr>
											</RowContextMenu>
										);
									})}
								</TableBody>
							</Table>
						{hasMore && (
							<div ref={desktopSentinelRef} className="py-3" />
						)}
					</div>
				</div>

				{/* Mobile Card View */}
					<div ref={mobileScrollRef} className="md:hidden divide-y divide-border/50 flex-1 overflow-auto">
						{sorted.map((doc, index) => {
							const isSelected = selectedIds.has(doc.id);
							const canSelect = isSelectable(doc);
							return (
								<RowContextMenu
									key={doc.id}
									doc={doc}
									onPreview={handleViewDocument}
									onDelete={setDeleteDoc}
									searchSpaceId={searchSpaceId}
								>
									<motion.div
										initial={!isSearchMode && index < 20 ? { opacity: 0 } : false}
										animate={{ opacity: 1 }}
										transition={!isSearchMode && index < 20 ? { duration: 0.15, delay: index * 0.03 } : { duration: 0 }}
										className={`px-3 py-2 transition-colors ${
											isSelected ? "bg-primary/5" : "hover:bg-muted/20"
										}`}
									>
										<div className="flex items-center gap-3">
											<Checkbox
												checked={isSelected}
												onCheckedChange={(v) =>
													canSelect && toggleOne(doc.id, !!v)
												}
												disabled={!canSelect}
												aria-label={
													canSelect
														? "Select row"
														: "Cannot select while processing"
												}
												className={`border-foreground data-[state=checked]:bg-primary data-[state=checked]:border-primary shrink-0 ${!canSelect ? "opacity-40 cursor-not-allowed" : ""}`}
											/>
											<div className="flex-1 min-w-0">
												<DocumentNameTooltip
													doc={doc}
													className="truncate block text-sm text-foreground cursor-default"
												/>
											</div>
											<div className="flex items-center gap-2 shrink-0">
												<Tooltip>
													<TooltipTrigger asChild>
														<span className="flex items-center justify-center">
															{getDocumentTypeIcon(
																doc.document_type,
																"h-4 w-4"
															)}
														</span>
													</TooltipTrigger>
													<TooltipContent side="top">
														{getDocumentTypeLabel(doc.document_type)}
													</TooltipContent>
												</Tooltip>
												<StatusIndicator status={doc.status} />
											</div>
										</div>
									</motion.div>
								</RowContextMenu>
							);
						})}
					{hasMore && (
						<div ref={mobileSentinelRef} className="py-3" />
					)}
				</div>
				</>
			)}

			{/* Document Content Viewer */}
			<Dialog open={!!viewingDoc} onOpenChange={(open) => !open && handleCloseViewer()}>
				<DialogContent className="max-w-4xl max-h-[80vh] flex flex-col overflow-hidden pb-0">
					<DialogHeader className="flex-shrink-0">
						<DialogTitle>{viewingDoc?.title}</DialogTitle>
					</DialogHeader>
					<div className="mt-4 overflow-y-auto flex-1 min-h-0 px-6 select-text">
						{viewingLoading ? (
							<div className="flex items-center justify-center py-12">
								<Spinner size="lg" className="text-muted-foreground" />
							</div>
						) : (
							<MarkdownViewer content={viewingContent} />
						)}
					</div>
				</DialogContent>
			</Dialog>

			{/* Delete Confirmation Dialog */}
			<AlertDialog open={!!deleteDoc} onOpenChange={(open) => !open && setDeleteDoc(null)}>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>Delete document?</AlertDialogTitle>
						<AlertDialogDescription>
							This action cannot be undone. This will permanently delete this document from
							your search space.
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel>Cancel</AlertDialogCancel>
						<AlertDialogAction
							onClick={(e) => {
								e.preventDefault();
								handleDeleteFromMenu();
							}}
							disabled={isDeleting}
							className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
						>
							{isDeleting ? "Deleting" : "Delete"}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</motion.div>
	);
}
