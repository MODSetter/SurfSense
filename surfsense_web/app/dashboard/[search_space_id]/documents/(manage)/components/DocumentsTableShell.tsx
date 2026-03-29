"use client";

import { useAtomValue, useSetAtom } from "jotai";
import {
	AlertCircle,
	CheckCircle2,
	ChevronDown,
	ChevronUp,
	Clock,
	Eye,
	FileText,
	FileX,
	MoreHorizontal,
	Network,
	PenLine,
	SearchX,
	Trash2,
	User,
} from "lucide-react";
import { useTranslations } from "next-intl";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { openEditorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import { membersAtom } from "@/atoms/members/members-query.atoms";
import { useDocumentUploadDialog } from "@/components/assistant-ui/document-upload-popup";
import { JsonMetadataViewer } from "@/components/json-metadata-viewer";
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
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Drawer,
	DrawerContent,
	DrawerHandle,
	DrawerHeader,
	DrawerTitle,
} from "@/components/ui/drawer";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import { useLongPress } from "@/hooks/use-long-press";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { getDocumentTypeIcon } from "./DocumentTypeIcon";
import type { Document, DocumentStatus } from "./types";

const EDITABLE_DOCUMENT_TYPES = ["FILE", "NOTE"] as const;
const NON_DELETABLE_DOCUMENT_TYPES = ["SURFSENSE_DOCS"] as const;

function getInitials(name: string): string {
	const parts = name.trim().split(/\s+/);
	if (parts.length >= 2) {
		return (parts[0][0] + parts[1][0]).toUpperCase();
	}
	return name.slice(0, 2).toUpperCase();
}

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
			className="flex items-center gap-1.5 text-left text-sm font-medium text-muted-foreground hover:text-muted-foreground transition-colors group"
		>
			{icon && <span>{icon}</span>}
			{children}
			<span
				className={`transition-opacity ${isActive ? "opacity-100" : "opacity-0 group-hover:opacity-50"}`}
			>
				{isActive && sortDesc ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
			</span>
		</button>
	);
}

function MobileCardWrapper({
	onLongPress,
	children,
}: {
	onLongPress: () => void;
	children: React.ReactNode;
}) {
	const { handlers, wasLongPress } = useLongPress(onLongPress);

	return (
		// biome-ignore lint/a11y/useSemanticElements: touch-only long-press wrapper for mobile
		<div
			role="group"
			onTouchStart={handlers.onTouchStart}
			onTouchMove={handlers.onTouchMove}
			onTouchEnd={(e) => {
				handlers.onTouchEnd();
				if (wasLongPress()) {
					e.preventDefault();
				}
			}}
			onContextMenu={(e) => e.preventDefault()}
		>
			{children}
		</div>
	);
}

export function DocumentsTableShell({
	documents,
	loading,
	error,
	sortKey,
	sortDesc,
	onSortChange,
	deleteDocument,
	bulkDeleteDocuments,
	searchSpaceId,
	hasMore = false,
	loadingMore = false,
	onLoadMore,
	mentionedDocIds,
	onToggleChatMention,
	isSearchMode = false,
	onOpenInTab,
}: {
	documents: Document[];
	loading: boolean;
	error: boolean;
	sortKey: SortKey;
	sortDesc: boolean;
	onSortChange: (key: SortKey) => void;
	deleteDocument: (id: number) => Promise<boolean>;
	bulkDeleteDocuments?: (ids: number[]) => Promise<{ success: number; failed: number }>;
	searchSpaceId: string;
	hasMore?: boolean;
	loadingMore?: boolean;
	onLoadMore?: () => void;
	/** IDs of documents currently mentioned as chips in the chat composer */
	mentionedDocIds?: Set<number>;
	/** Toggle a document's mention in the chat (add if not mentioned, remove if mentioned) */
	onToggleChatMention?: (doc: Document, mentioned: boolean) => void;
	/** Whether results are filtered by a search query or type filters */
	isSearchMode?: boolean;
	/** When provided, desktop "Preview" opens a document tab instead of the popup dialog */
	onOpenInTab?: (doc: Document) => void;
}) {
	const t = useTranslations("documents");
	const { openDialog } = useDocumentUploadDialog();

	const [viewingDoc, setViewingDoc] = useState<Document | null>(null);
	const [viewingContent, setViewingContent] = useState<string>("");
	const [viewingLoading, setViewingLoading] = useState(false);

	const [metadataDoc, setMetadataDoc] = useState<Document | null>(null);
	const [metadataJson, setMetadataJson] = useState<Record<string, unknown> | null>(null);
	const [metadataLoading, setMetadataLoading] = useState(false);
	const [previewScrollPos, setPreviewScrollPos] = useState<"top" | "middle" | "bottom">("top");
	const handlePreviewScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
		const el = e.currentTarget;
		const atTop = el.scrollTop <= 2;
		const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= 2;
		setPreviewScrollPos(atTop ? "top" : atBottom ? "bottom" : "middle");
	}, []);

	const [deleteDoc, setDeleteDoc] = useState<Document | null>(null);
	const [isDeleting, setIsDeleting] = useState(false);
	const [mobileActionDoc, setMobileActionDoc] = useState<Document | null>(null);
	const [bulkDeleteConfirmOpen, setBulkDeleteConfirmOpen] = useState(false);
	const [isBulkDeleting, setIsBulkDeleting] = useState(false);
	const openEditor = useSetAtom(openEditorPanelAtom);
	const [openMenuDocId, setOpenMenuDocId] = useState<number | null>(null);

	const { data: members } = useAtomValue(membersAtom);
	const memberMap = useMemo(() => {
		const map = new Map<string, { name: string; email?: string; avatarUrl?: string }>();
		if (members) {
			for (const m of members) {
				map.set(m.user_id, {
					name: m.user_display_name || m.user_email || "Unknown",
					email: m.user_email || undefined,
					avatarUrl: m.user_avatar_url || undefined,
				});
			}
		}
		return map;
	}, [members]);

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

		return () => {
			for (const o of observers) o.disconnect();
		};
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

	const handleViewMetadata = useCallback(async (doc: Document) => {
		setMetadataDoc(doc);
		setMetadataLoading(true);
		try {
			const fullDoc = await documentsApiService.getDocument({ id: doc.id });
			setMetadataJson(fullDoc.document_metadata ?? {});
		} catch (err) {
			console.error("[DocumentsTableShell] Failed to fetch document metadata:", err);
			setMetadataJson({ error: "Failed to load document metadata" });
		} finally {
			setMetadataLoading(false);
		}
	}, []);

	const handleDeleteFromMenu = useCallback(async () => {
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
	}, [deleteDoc, deleteDocument]);

	const sorted = React.useMemo(
		() => sortDocuments(documents, sortKey, sortDesc),
		[documents, sortKey, sortDesc]
	);

	const isSelectable = (doc: Document) => {
		const state = doc.status?.state;
		return state !== "pending" && state !== "processing";
	};

	const hasChatMode = !!onToggleChatMention && !!mentionedDocIds;

	const selectableDocs = sorted.filter(isSelectable);
	const allMentionedOnPage =
		hasChatMode &&
		selectableDocs.length > 0 &&
		selectableDocs.every((d) => mentionedDocIds.has(d.id));
	const someMentionedOnPage =
		hasChatMode && selectableDocs.some((d) => mentionedDocIds.has(d.id)) && !allMentionedOnPage;

	const toggleAll = (checked: boolean) => {
		if (!onToggleChatMention) return;
		for (const doc of selectableDocs) {
			const isMentioned = mentionedDocIds?.has(doc.id) ?? false;
			if (checked && !isMentioned) {
				onToggleChatMention(doc, false);
			} else if (!checked && isMentioned) {
				onToggleChatMention(doc, true);
			}
		}
	};

	const onSortHeader = (key: SortKey) => onSortChange(key);

	const deletableSelectedIds = React.useMemo(() => {
		if (!mentionedDocIds || mentionedDocIds.size === 0) return [];
		return sorted
			.filter((doc) => {
				if (!mentionedDocIds.has(doc.id)) return false;
				const state = doc.status?.state;
				return (
					state !== "pending" &&
					state !== "processing" &&
					!NON_DELETABLE_DOCUMENT_TYPES.includes(
						doc.document_type as (typeof NON_DELETABLE_DOCUMENT_TYPES)[number]
					)
				);
			})
			.map((doc) => doc.id);
	}, [sorted, mentionedDocIds]);

	const hasDeletableSelection = deletableSelectedIds.length > 0;

	const handleBulkDelete = useCallback(async () => {
		if (deletableSelectedIds.length === 0) return;
		setIsBulkDeleting(true);
		try {
			if (bulkDeleteDocuments) {
				const { success, failed } = await bulkDeleteDocuments(deletableSelectedIds);
				if (success > 0) {
					toast.success(`Deleted ${success} document${success !== 1 ? "s" : ""}`);
				}
				if (failed > 0) {
					toast.error(`Failed to delete ${failed} document${failed !== 1 ? "s" : ""}`);
				}
			} else {
				const results = await Promise.allSettled(
					deletableSelectedIds.map((id) => deleteDocument(id))
				);
				const successCount = results.filter(
					(r) => r.status === "fulfilled" && r.value === true
				).length;
				const failCount = deletableSelectedIds.length - successCount;
				if (successCount > 0) {
					toast.success(`Deleted ${successCount} document${successCount !== 1 ? "s" : ""}`);
				}
				if (failCount > 0) {
					toast.error(`Failed to delete ${failCount} document${failCount !== 1 ? "s" : ""}`);
				}
			}
		} catch {
			toast.error("Failed to delete documents");
		}
		setIsBulkDeleting(false);
		setBulkDeleteConfirmOpen(false);
	}, [deletableSelectedIds, bulkDeleteDocuments, deleteDocument]);

	const bulkDeleteBar = hasDeletableSelection ? (
		<div className="absolute inset-x-0 top-0 z-10 flex items-center justify-center py-1 pointer-events-none animate-in fade-in duration-150">
			<button
				type="button"
				onClick={() => setBulkDeleteConfirmOpen(true)}
				className="pointer-events-auto flex items-center gap-1.5 px-3 py-1 rounded-md bg-destructive text-destructive-foreground shadow-lg text-xs font-medium hover:bg-destructive/90 transition-colors"
			>
				<Trash2 size={12} />
				Delete {deletableSelectedIds.length} {deletableSelectedIds.length === 1 ? "item" : "items"}
			</button>
		</div>
	) : null;

	return (
		<div className="bg-sidebar overflow-hidden select-none border-t border-border/50 flex-1 flex flex-col min-h-0">
			{/* Desktop Table View */}
			<div className="hidden md:flex md:flex-col flex-1 min-h-0">
				<Table className="table-fixed w-full">
					<TableHeader>
						<TableRow className="hover:bg-transparent border-b border-border/50">
							<TableHead className="w-10 pl-3 pr-0 text-center h-8">
								<div className="flex items-center justify-center h-full">
									<Checkbox
										checked={allMentionedOnPage || (someMentionedOnPage && "indeterminate")}
										onCheckedChange={(v) => toggleAll(!!v)}
										aria-label={hasChatMode ? "Toggle all for chat" : "Select all"}
										className="shrink-0"
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
									<Network size={14} className="text-muted-foreground" />
								</span>
							</TableHead>
							<TableHead className="w-10 text-center h-8 px-0 pr-2">
								<span className="flex items-center justify-center">
									<User size={14} className="text-muted-foreground" />
								</span>
							</TableHead>
						</TableRow>
					</TableHeader>
				</Table>
				{loading ? (
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
										<TableCell className="w-10 px-0 pr-2 py-1.5 text-center">
											<Skeleton className="h-5 w-5 mx-auto rounded-full" />
										</TableCell>
									</TableRow>
								))}
							</TableBody>
						</Table>
					</div>
				) : error ? (
					<div className="flex flex-1 w-full items-center justify-center">
						<div className="flex flex-col items-center gap-3">
							<AlertCircle className="h-8 w-8 text-destructive" />
							<p className="text-sm text-destructive">{t("error_loading")}</p>
						</div>
					</div>
				) : sorted.length === 0 ? (
					<div className="flex flex-1 w-full items-center justify-center">
						{isSearchMode ? (
							<div className="flex flex-col items-center gap-3 max-w-md px-4 text-center">
								<SearchX className="h-8 w-8 text-muted-foreground" />
								<div className="space-y-1">
									<h3 className="text-sm font-medium text-muted-foreground">
										No matching documents
									</h3>
									<p className="text-xs text-muted-foreground/70">
										Try a different search term or adjust your filters.
									</p>
								</div>
							</div>
						) : (
							<div className="flex flex-col items-center gap-4 max-w-md px-4 text-center">
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
									Upload Documents
								</Button>
							</div>
						)}
					</div>
				) : (
					<div ref={desktopScrollRef} className="flex-1 overflow-auto relative">
						{bulkDeleteBar}
						<Table className="table-fixed w-full">
							<TableBody>
								{sorted.map((doc) => {
									const isMentioned = mentionedDocIds?.has(doc.id) ?? false;
									const canInteract = isSelectable(doc);
									const isBeingProcessed =
										doc.status?.state === "pending" || doc.status?.state === "processing";
									const isFileFailed =
										doc.document_type === "FILE" && doc.status?.state === "failed";
									const isEditable = EDITABLE_DOCUMENT_TYPES.includes(
										doc.document_type as (typeof EDITABLE_DOCUMENT_TYPES)[number]
									);
									const shouldShowDelete = !NON_DELETABLE_DOCUMENT_TYPES.includes(
										doc.document_type as (typeof NON_DELETABLE_DOCUMENT_TYPES)[number]
									);
									const isMenuOpen = openMenuDocId === doc.id;
									const handleRowToggle = () => {
										if (canInteract && onToggleChatMention) {
											onToggleChatMention(doc, isMentioned);
										}
									};
									const handleRowClick = (e: React.MouseEvent) => {
										if (e.ctrlKey || e.metaKey) {
											e.preventDefault();
											e.stopPropagation();
											handleViewMetadata(doc);
											return;
										}
										handleRowToggle();
									};
									return (
										<tr
											key={doc.id}
											className={`group border-b border-border/50 transition-colors ${
												isMentioned ? "bg-primary/5 hover:bg-primary/8" : "hover:bg-muted/30"
											} ${canInteract && hasChatMode ? "cursor-pointer" : ""}`}
											onClick={handleRowClick}
										>
											<TableCell
												className="w-10 pl-3 pr-0 py-1.5 text-center"
												onClick={(e) => e.stopPropagation()}
											>
												<div className="flex items-center justify-center h-full">
													{(() => {
														const state = doc.status?.state ?? "ready";
														if (state === "pending" || state === "processing") {
															return <StatusIndicator status={doc.status} />;
														}
														if (state === "failed") {
															if (isMentioned) {
																return (
																	<Checkbox
																		checked={isMentioned}
																		onCheckedChange={() => handleRowToggle()}
																		aria-label="Remove from chat"
																		className="shrink-0"
																	/>
																);
															}
															return (
																<>
																	<span className="group-hover:hidden">
																		<StatusIndicator status={doc.status} />
																	</span>
																	<span className="hidden group-hover:inline-flex">
																		<Checkbox
																			checked={isMentioned}
																			onCheckedChange={() => handleRowToggle()}
																			aria-label="Add to chat"
																			className="shrink-0"
																		/>
																	</span>
																</>
															);
														}
														return (
															<Checkbox
																checked={isMentioned}
																onCheckedChange={() => handleRowToggle()}
																aria-label={isMentioned ? "Remove from chat" : "Add to chat"}
																className="shrink-0"
															/>
														);
													})()}
												</div>
											</TableCell>
											<TableCell className="px-2 py-1.5 max-w-0">
												<span className="truncate block text-sm text-foreground cursor-default">
													{doc.title}
												</span>
											</TableCell>
											<TableCell className="w-10 px-0 py-1.5 text-center">
												<span className="flex items-center justify-center">
													{getDocumentTypeIcon(doc.document_type, "h-4 w-4")}
												</span>
											</TableCell>
											<TableCell
												className="w-10 px-0 pr-2 py-1.5 text-center"
												onClick={(e) => e.stopPropagation()}
											>
												<div className="relative flex items-center justify-center">
													{(() => {
														const member = doc.created_by_id
															? memberMap.get(doc.created_by_id)
															: null;
														const displayName =
															member?.name ||
															doc.created_by_name ||
															doc.created_by_email ||
															"Unknown";
														const avatarUrl = member?.avatarUrl;
														const email = member?.email || doc.created_by_email || displayName;
														return (
															<Tooltip>
																<TooltipTrigger asChild>
																	<span
																		className={`flex items-center justify-center ${isMenuOpen ? "invisible" : "group-hover:invisible"}`}
																	>
																		<Avatar className="size-5 shrink-0">
																			{avatarUrl && (
																				<AvatarImage src={avatarUrl} alt={displayName} />
																			)}
																			<AvatarFallback className="text-[9px]">
																				{getInitials(displayName)}
																			</AvatarFallback>
																		</Avatar>
																	</span>
																</TooltipTrigger>
																<TooltipContent side="top">{email}</TooltipContent>
															</Tooltip>
														);
													})()}
													<div
														className={`absolute inset-0 flex items-center justify-center ${isMenuOpen ? "visible" : "invisible group-hover:visible"}`}
													>
														<DropdownMenu
															onOpenChange={(open) => setOpenMenuDocId(open ? doc.id : null)}
														>
															<DropdownMenuTrigger asChild>
																<button
																	type="button"
																	className="flex items-center justify-center h-6 w-6 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
																>
																	<MoreHorizontal size={14} />
																</button>
															</DropdownMenuTrigger>
															<DropdownMenuContent align="end" className="w-48">
																<DropdownMenuItem onClick={() => onOpenInTab ? onOpenInTab(doc) : handleViewDocument(doc)}>
																	<Eye className="h-4 w-4" />
																	Open
																</DropdownMenuItem>
																{isEditable && (
																	<DropdownMenuItem
																		onClick={() => {
																			if (!(isBeingProcessed || isFileFailed)) {
																				openEditor({
																					documentId: doc.id,
																					searchSpaceId: Number(searchSpaceId),
																					title: doc.title,
																				});
																			}
																		}}
																		disabled={isBeingProcessed || isFileFailed}
																	>
																		<PenLine className="h-4 w-4" />
																		Edit
																	</DropdownMenuItem>
																)}
																{shouldShowDelete && (
																	<DropdownMenuItem
																		onClick={() => !isBeingProcessed && setDeleteDoc(doc)}
																		disabled={isBeingProcessed}
																		className=""
																	>
																		<Trash2 className="h-4 w-4" />
																		Delete
																	</DropdownMenuItem>
																)}
															</DropdownMenuContent>
														</DropdownMenu>
													</div>
												</div>
											</TableCell>
										</tr>
									);
								})}
							</TableBody>
						</Table>
						{hasMore && <div ref={desktopSentinelRef} className="py-3" />}
					</div>
				)}
			</div>

			{/* Mobile Card View */}
			{loading ? (
				<div className="md:hidden divide-y divide-border/50 flex-1 overflow-auto">
					{[70, 85, 55, 78, 62, 90].map((widthPercent) => (
						<div key={`skeleton-mobile-${widthPercent}`} className="px-3 py-2">
							<div className="flex items-center gap-3">
								<Skeleton className="h-4 w-4 rounded shrink-0" />
								<div className="flex-1 min-w-0">
									<Skeleton className="h-4" style={{ width: `${widthPercent}%` }} />
								</div>
								<Skeleton className="h-4 w-4 rounded shrink-0" />
								<Skeleton className="h-5 w-5 rounded-full shrink-0" />
							</div>
						</div>
					))}
				</div>
			) : error ? (
				<div className="md:hidden flex flex-1 w-full items-center justify-center">
					<div className="flex flex-col items-center gap-3">
						<AlertCircle className="h-8 w-8 text-destructive" />
						<p className="text-sm text-destructive">{t("error_loading")}</p>
					</div>
				</div>
			) : sorted.length === 0 ? (
				<div className="md:hidden flex flex-1 w-full items-center justify-center">
					{isSearchMode ? (
						<div className="flex flex-col items-center gap-3 max-w-md px-4 text-center">
							<SearchX className="h-8 w-8 text-muted-foreground" />
							<div className="space-y-1">
								<h3 className="text-sm font-medium text-muted-foreground">No matching documents</h3>
								<p className="text-xs text-muted-foreground/70">
									Try a different search term or adjust your filters.
								</p>
							</div>
						</div>
					) : (
						<div className="flex flex-col items-center gap-4 max-w-md px-4 text-center">
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
								Upload Documents
							</Button>
						</div>
					)}
				</div>
			) : (
				<div
					ref={mobileScrollRef}
					className="md:hidden divide-y divide-border/50 flex-1 overflow-auto relative"
				>
					{bulkDeleteBar}
					{sorted.map((doc) => {
						const isMentioned = mentionedDocIds?.has(doc.id) ?? false;
						const statusState = doc.status?.state ?? "ready";
						const showCheckbox = statusState === "ready";
						const canInteract = showCheckbox;
						const handleCardClick = (e?: React.MouseEvent) => {
							if (e && (e.ctrlKey || e.metaKey)) {
								e.preventDefault();
								e.stopPropagation();
								handleViewMetadata(doc);
								return;
							}
							if (canInteract && onToggleChatMention) {
								onToggleChatMention(doc, isMentioned);
							}
						};
						return (
							<MobileCardWrapper key={doc.id} onLongPress={() => setMobileActionDoc(doc)}>
								<div
									className={`relative px-3 py-2 transition-colors ${
										isMentioned ? "bg-primary/5" : "hover:bg-muted/20"
									} ${canInteract && hasChatMode ? "cursor-pointer" : ""}`}
								>
									{canInteract && hasChatMode && (
										<button
											type="button"
											className="absolute inset-0 z-0"
											aria-label={
												isMentioned ? `Remove ${doc.title} from chat` : `Add ${doc.title} to chat`
											}
											onClick={handleCardClick}
										/>
									)}
									<div className="relative z-10 flex items-center gap-3 pointer-events-none">
										<span className="pointer-events-auto shrink-0">
											{showCheckbox ? (
												<Checkbox
													checked={isMentioned}
													onCheckedChange={() => handleCardClick()}
													aria-label={isMentioned ? "Remove from chat" : "Add to chat"}
													className="shrink-0"
												/>
											) : (
												<StatusIndicator status={doc.status} />
											)}
										</span>
										<div className="flex-1 min-w-0">
											<span className="truncate block text-sm text-foreground">{doc.title}</span>
										</div>
										<span className="flex items-center justify-center shrink-0">
											{getDocumentTypeIcon(doc.document_type, "h-4 w-4")}
										</span>
										{(() => {
											const member = doc.created_by_id ? memberMap.get(doc.created_by_id) : null;
											const displayName =
												member?.name || doc.created_by_name || doc.created_by_email || "Unknown";
											const avatarUrl = member?.avatarUrl;
											return (
												<span className="flex items-center justify-center shrink-0">
													<Avatar className="size-5">
														{avatarUrl && <AvatarImage src={avatarUrl} alt={displayName} />}
														<AvatarFallback className="text-[9px]">
															{getInitials(displayName)}
														</AvatarFallback>
													</Avatar>
												</span>
											);
										})()}
									</div>
								</div>
							</MobileCardWrapper>
						);
					})}
					{hasMore && <div ref={mobileSentinelRef} className="py-3" />}
				</div>
			)}

			{/* Document Content Viewer (mobile drawer) */}
			<Drawer open={!!viewingDoc} onOpenChange={(open) => !open && handleCloseViewer()}>
				<DrawerContent className="max-h-[85vh] flex flex-col">
					<DrawerHandle />
					<DrawerHeader className="text-left shrink-0">
						<DrawerTitle className="text-base leading-tight break-words">
							{viewingDoc?.title}
						</DrawerTitle>
					</DrawerHeader>
					<div
						onScroll={handlePreviewScroll}
						className="overflow-y-auto flex-1 min-h-0 px-4 pb-6 select-text text-xs [&_h1]:text-base! [&_h1]:mt-3! [&_h2]:text-sm! [&_h2]:mt-2! [&_h3]:text-xs! [&_h3]:mt-2! [&_h4]:text-xs! [&_td]:text-[11px]! [&_td]:px-2! [&_td]:py-1.5! [&_th]:text-[11px]! [&_th]:px-2! [&_th]:py-1.5!"
						style={{
							maskImage: `linear-gradient(to bottom, ${previewScrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${previewScrollPos === "bottom" ? "black" : "transparent"})`,
							WebkitMaskImage: `linear-gradient(to bottom, ${previewScrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${previewScrollPos === "bottom" ? "black" : "transparent"})`,
						}}
					>
						{viewingLoading ? (
							<div className="flex items-center justify-center py-12">
								<Spinner size="lg" className="text-muted-foreground" />
							</div>
						) : (
							<MarkdownViewer content={viewingContent} />
						)}
					</div>
				</DrawerContent>
			</Drawer>

			{/* Document Metadata Viewer (Ctrl+Click) */}
			<JsonMetadataViewer
				title={metadataDoc?.title ?? "Document"}
				metadata={metadataJson}
				loading={metadataLoading}
				open={!!metadataDoc}
				onOpenChange={(open) => {
					if (!open) {
						setMetadataDoc(null);
						setMetadataJson(null);
						setMetadataLoading(false);
					}
				}}
			/>

			{/* Delete Confirmation Dialog */}
			<AlertDialog open={!!deleteDoc} onOpenChange={(open) => !open && setDeleteDoc(null)}>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>Delete document?</AlertDialogTitle>
						<AlertDialogDescription>
							This action cannot be undone. This will permanently delete this document from your
							search space.
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
							className="relative bg-destructive text-destructive-foreground hover:bg-destructive/90"
						>
							<span className={isDeleting ? "opacity-0" : ""}>Delete</span>
							{isDeleting && <Spinner size="sm" className="absolute" />}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>

			{/* Mobile Document Actions Drawer */}
			<Drawer open={!!mobileActionDoc} onOpenChange={(open) => !open && setMobileActionDoc(null)}>
				<DrawerContent>
					<DrawerHandle />
					<DrawerHeader className="text-left">
						<DrawerTitle className="break-words text-base">{mobileActionDoc?.title}</DrawerTitle>
						<div className="space-y-0.5 text-xs mt-1">
							<p>
								<span className="text-muted-foreground">Owner:</span>{" "}
								{mobileActionDoc?.created_by_name || mobileActionDoc?.created_by_email || "—"}
							</p>
							<p>
								<span className="text-muted-foreground">Created:</span>{" "}
								{mobileActionDoc ? formatAbsoluteDate(mobileActionDoc.created_at) : ""}
							</p>
						</div>
					</DrawerHeader>
					<div className="px-4 pb-6 flex flex-col gap-2">
						<Button
							variant="secondary"
							className="justify-start gap-2"
							onClick={() => {
								if (mobileActionDoc) handleViewDocument(mobileActionDoc);
								setMobileActionDoc(null);
							}}
						>
							<Eye className="h-4 w-4" />
							Open
						</Button>
						{mobileActionDoc &&
							EDITABLE_DOCUMENT_TYPES.includes(
								mobileActionDoc.document_type as (typeof EDITABLE_DOCUMENT_TYPES)[number]
							) && (
								<Button
									variant="secondary"
									className="justify-start gap-2"
									disabled={
										mobileActionDoc.status?.state === "pending" ||
										mobileActionDoc.status?.state === "processing" ||
										(mobileActionDoc.document_type === "FILE" &&
											mobileActionDoc.status?.state === "failed")
									}
									onClick={() => {
										if (mobileActionDoc) {
											openEditor({
												documentId: mobileActionDoc.id,
												searchSpaceId: Number(searchSpaceId),
												title: mobileActionDoc.title,
											});
											setMobileActionDoc(null);
										}
									}}
								>
									<PenLine className="h-4 w-4" />
									Edit
								</Button>
							)}
						{mobileActionDoc &&
							!NON_DELETABLE_DOCUMENT_TYPES.includes(
								mobileActionDoc.document_type as (typeof NON_DELETABLE_DOCUMENT_TYPES)[number]
							) && (
								<Button
									variant="destructive"
									className="justify-start gap-2"
									disabled={
										mobileActionDoc.status?.state === "pending" ||
										mobileActionDoc.status?.state === "processing"
									}
									onClick={() => {
										if (mobileActionDoc) {
											setDeleteDoc(mobileActionDoc);
											setMobileActionDoc(null);
										}
									}}
								>
									<Trash2 className="h-4 w-4" />
									Delete
								</Button>
							)}
					</div>
				</DrawerContent>
			</Drawer>

			{/* Bulk Delete Confirmation Dialog */}
			<AlertDialog
				open={bulkDeleteConfirmOpen}
				onOpenChange={(open) => !open && !isBulkDeleting && setBulkDeleteConfirmOpen(false)}
			>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>
							Delete {deletableSelectedIds.length} document
							{deletableSelectedIds.length !== 1 ? "s" : ""}?
						</AlertDialogTitle>
						<AlertDialogDescription>
							This action cannot be undone.{" "}
							{deletableSelectedIds.length === 1
								? "This document"
								: `These ${deletableSelectedIds.length} documents`}{" "}
							will be permanently deleted from your search space.
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel disabled={isBulkDeleting}>Cancel</AlertDialogCancel>
						<AlertDialogAction
							onClick={(e) => {
								e.preventDefault();
								handleBulkDelete();
							}}
							disabled={isBulkDeleting}
							className="relative bg-destructive text-destructive-foreground hover:bg-destructive/90"
						>
							<span className={isBulkDeleting ? "opacity-0" : ""}>Delete</span>
							{isBulkDeleting && <Spinner size="sm" className="absolute" />}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</div>
	);
}
