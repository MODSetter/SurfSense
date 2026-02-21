"use client";

import { formatDistanceToNow } from "date-fns";
import {
	AlertCircle,
	BadgeInfo,
	Calendar,
	CheckCircle2,
	ChevronDown,
	ChevronUp,
	Clock,
	FileText,
	FileX,
	Network,
	Plus,
	User,
} from "lucide-react";
import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useDocumentUploadDialog } from "@/components/assistant-ui/document-upload-popup";
import { JsonMetadataViewer } from "@/components/json-metadata-viewer";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { DocumentTypeChip } from "./DocumentTypeIcon";
import { RowActions } from "./RowActions";
import type { ColumnVisibility, Document, DocumentStatus } from "./types";

// Status indicator component for document processing status
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
			<span
				className={`transition-opacity ${isActive ? "opacity-100" : "opacity-0 group-hover:opacity-50"}`}
			>
				{isActive && sortDesc ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
			</span>
		</button>
	);
}

export function DocumentsTableShell({
	documents,
	loading,
	error,
	selectedIds,
	setSelectedIds,
	columnVisibility,
	sortKey,
	sortDesc,
	onSortChange,
	deleteDocument,
	searchSpaceId,
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
}) {
	const t = useTranslations("documents");
	const { openDialog } = useDocumentUploadDialog();

	// State for metadata viewer (opened via Ctrl/Cmd+Click)
	// Real-time documents don't sync metadata - we fetch on-demand when viewing
	const [metadataDoc, setMetadataDoc] = useState<Document | null>(null);
	const [metadataContent, setMetadataContent] = useState<any>(null);
	const [metadataLoading, setMetadataLoading] = useState(false);

	// State for lazy document content viewer
	// Real-time documents don't sync content - we fetch on-demand when viewing
	const [viewingDoc, setViewingDoc] = useState<Document | null>(null);
	const [viewingContent, setViewingContent] = useState<string>("");
	const [viewingLoading, setViewingLoading] = useState(false);

	// Fetch document metadata on-demand when metadata viewer is opened
	const handleViewMetadata = useCallback(async (doc: Document) => {
		setMetadataDoc(doc);

		// If metadata is already available (from API/search), use it directly
		if (doc.document_metadata) {
			setMetadataContent(doc.document_metadata);
			return;
		}

		// Otherwise, fetch from API (lazy loading for real-time synced documents)
		setMetadataLoading(true);
		try {
			const fullDoc = await documentsApiService.getDocument({ id: doc.id });
			setMetadataContent(fullDoc.document_metadata);
		} catch (err) {
			console.error("[DocumentsTableShell] Failed to fetch document metadata:", err);
			setMetadataContent(null);
		} finally {
			setMetadataLoading(false);
		}
	}, []);

	// Close metadata viewer
	const handleCloseMetadata = useCallback(() => {
		setMetadataDoc(null);
		setMetadataContent(null);
		setMetadataLoading(false);
	}, []);

	// Fetch document content on-demand when viewer is opened
	const handleViewDocument = useCallback(async (doc: Document) => {
		setViewingDoc(doc);

		// If content is already available (from API/search), use it directly
		if (doc.content) {
			setViewingContent(doc.content);
			return;
		}

		// Otherwise, fetch from API (lazy loading for real-time synced documents)
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

	// Close document viewer
	const handleCloseViewer = useCallback(() => {
		setViewingDoc(null);
		setViewingContent("");
		setViewingLoading(false);
	}, []);

	const sorted = React.useMemo(
		() => sortDocuments(documents, sortKey, sortDesc),
		[documents, sortKey, sortDesc]
	);

	// Helper: check if document can be selected (not processing/pending)
	const isSelectable = (doc: Document) => {
		const state = doc.status?.state;
		return state !== "pending" && state !== "processing";
	};

	// Only consider selectable documents for "select all" logic
	const selectableDocs = sorted.filter(isSelectable);
	const allSelectedOnPage =
		selectableDocs.length > 0 && selectableDocs.every((d) => selectedIds.has(d.id));
	const someSelectedOnPage =
		selectableDocs.some((d) => selectedIds.has(d.id)) && !allSelectedOnPage;

	const toggleAll = (checked: boolean) => {
		const next = new Set(selectedIds);
		if (checked)
			// Only select documents that are not processing/pending
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
			className="rounded-lg border border-border/40 bg-background overflow-hidden select-none"
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
								<TableRow className="hover:bg-transparent border-b border-border/40">
									<TableHead className="w-8 px-0 text-center">
										<div className="flex items-center justify-center h-full">
											<Skeleton className="h-4 w-4 rounded" />
										</div>
									</TableHead>
									<TableHead className="w-[40%] max-w-0 border-r border-border/40">
										<Skeleton className="h-3 w-20" />
									</TableHead>
									{columnVisibility.document_type && (
										<TableHead className="w-[15%] min-w-[100px] max-w-[170px] border-r border-border/40">
											<Skeleton className="h-3 w-14" />
										</TableHead>
									)}
									{columnVisibility.created_by && (
										<TableHead className="w-36 border-r border-border/40">
											<Skeleton className="h-3 w-10" />
										</TableHead>
									)}
									{columnVisibility.created_at && (
										<TableHead className="w-32 border-r border-border/40">
											<Skeleton className="h-3 w-16" />
										</TableHead>
									)}
									{columnVisibility.status && (
										<TableHead className="w-14 text-center">
											<Skeleton className="h-3 w-12 mx-auto" />
										</TableHead>
									)}
									<TableHead className="w-10">
										<span className="sr-only">Actions</span>
									</TableHead>
								</TableRow>
							</TableHeader>
						</Table>
						<div className="h-[50vh] overflow-auto">
							<Table className="table-fixed w-full">
								<TableBody>
									{[65, 80, 45, 72, 55, 88, 40, 60, 50, 75].map((widthPercent, index) => (
										<TableRow
											key={`skeleton-${index}`}
											className="border-b border-border/40 hover:bg-transparent"
										>
											<TableCell className="w-8 px-0 py-2.5 text-center">
												<div className="flex items-center justify-center h-full">
													<Skeleton className="h-4 w-4 rounded" />
												</div>
											</TableCell>
											<TableCell className="w-[40%] py-2.5 max-w-0 border-r border-border/40">
												<Skeleton className="h-4" style={{ width: `${widthPercent}%` }} />
											</TableCell>
											{columnVisibility.document_type && (
												<TableCell className="w-[15%] min-w-[100px] max-w-[170px] py-2.5 border-r border-border/40 overflow-hidden">
													<Skeleton className="h-5 w-24 rounded" />
												</TableCell>
											)}
											{columnVisibility.created_by && (
												<TableCell className="w-36 py-2.5 truncate border-r border-border/40">
													<Skeleton className="h-4 w-20" />
												</TableCell>
											)}
											{columnVisibility.created_at && (
												<TableCell className="w-32 py-2.5 border-r border-border/40">
													<Skeleton className="h-4 w-20" />
												</TableCell>
											)}
											{columnVisibility.status && (
												<TableCell className="w-14 py-2.5 text-center">
													<Skeleton className="h-5 w-5 mx-auto rounded-full" />
												</TableCell>
											)}
											<TableCell className="w-10 py-2.5 text-center">
												<Skeleton className="h-6 w-6 mx-auto rounded" />
											</TableCell>
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
										<Skeleton className="h-4" style={{ width: `${widthPercent}%` }} />
										<div className="flex flex-wrap items-center gap-2">
											<Skeleton className="h-5 w-20 rounded" />
											{columnVisibility.created_by && <Skeleton className="h-3 w-14" />}
											{columnVisibility.created_at && <Skeleton className="h-3 w-20" />}
										</div>
									</div>
									<div className="flex items-center gap-2">
										{columnVisibility.status && <Skeleton className="h-5 w-5 rounded-full" />}
										<Skeleton className="h-7 w-7 rounded" />
									</div>
								</div>
							</div>
						))}
					</div>
				</>
			) : error ? (
				<div className="flex h-[50vh] w-full items-center justify-center">
					<div className="flex flex-col items-center gap-3">
						<AlertCircle className="h-8 w-8 text-destructive" />
						<p className="text-sm text-destructive">{t("error_loading")}</p>
					</div>
				</div>
			) : sorted.length === 0 ? (
				<div className="flex h-[50vh] w-full items-center justify-center">
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
					<div className="hidden md:flex md:flex-col">
						{/* Fixed Header */}
						<Table className="table-fixed w-full">
							<TableHeader>
								<TableRow className="hover:bg-transparent border-b border-border/40">
									<TableHead className="w-8 px-0 text-center">
										<div className="flex items-center justify-center h-full">
											<Checkbox
												checked={allSelectedOnPage || (someSelectedOnPage && "indeterminate")}
												onCheckedChange={(v) => toggleAll(!!v)}
												aria-label="Select all"
												className="border-foreground data-[state=checked]:bg-primary data-[state=checked]:border-primary"
											/>
										</div>
									</TableHead>
									<TableHead className="w-[40%] border-r border-border/40">
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
										<TableHead className="w-[15%] min-w-[100px] max-w-[170px] border-r border-border/40">
											<SortableHeader
												sortKey="document_type"
												currentSortKey={sortKey}
												sortDesc={sortDesc}
												onSort={onSortHeader}
												icon={<Network size={14} className="text-muted-foreground" />}
											>
												Source
											</SortableHeader>
										</TableHead>
									)}
									{columnVisibility.created_by && (
										<TableHead className="w-36 border-r border-border/40">
											<span className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground/70">
												<User size={14} className="opacity-60 text-muted-foreground" />
												User
											</span>
										</TableHead>
									)}
									{columnVisibility.created_at && (
										<TableHead className="w-32 border-r border-border/40">
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
									{columnVisibility.status && (
										<TableHead className="w-14">
											<span className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground/70">
												<BadgeInfo size={14} className="opacity-60 text-muted-foreground" />
												Status
											</span>
										</TableHead>
									)}
									<TableHead className="w-10">
										<span className="sr-only">Actions</span>
									</TableHead>
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
										const canSelect = isSelectable(doc);
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
												className={`border-b border-border/40 transition-colors ${
													isSelected ? "bg-primary/5 hover:bg-primary/8" : "hover:bg-muted/30"
												}`}
											>
												<TableCell className="w-8 px-0 py-2.5 text-center">
													<div className="flex items-center justify-center h-full">
														<Checkbox
															checked={isSelected}
															onCheckedChange={(v) => canSelect && toggleOne(doc.id, !!v)}
															disabled={!canSelect}
															aria-label={
																canSelect ? "Select row" : "Cannot select while processing"
															}
															className={`border-foreground data-[state=checked]:bg-primary data-[state=checked]:border-primary ${!canSelect ? "opacity-40 cursor-not-allowed" : ""}`}
														/>
													</div>
												</TableCell>
												<TableCell className="w-[40%] py-2.5 max-w-0 border-r border-border/40">
													<button
														type="button"
														className="block w-full text-left text-sm text-foreground hover:text-foreground transition-colors cursor-pointer bg-transparent border-0 p-0 truncate"
														onClick={(e) => {
															// Ctrl (Win/Linux) or Cmd (Mac) + Click opens metadata
															if (e.ctrlKey || e.metaKey) {
																e.preventDefault();
																e.stopPropagation();
																handleViewMetadata(doc);
															} else {
																// Normal click opens document viewer (lazy loads content)
																handleViewDocument(doc);
															}
														}}
														onKeyDown={(e) => {
															// Ctrl/Cmd + Enter opens metadata
															if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
																e.preventDefault();
																handleViewMetadata(doc);
															} else if (e.key === "Enter") {
																// Enter opens document viewer
																handleViewDocument(doc);
															}
														}}
													>
														<TruncatedText text={title} className="truncate block" />
													</button>
												</TableCell>
												{columnVisibility.document_type && (
													<TableCell className="w-[15%] min-w-[100px] max-w-[170px] py-2.5 border-r border-border/40 overflow-hidden">
														<DocumentTypeChip type={doc.document_type} />
													</TableCell>
												)}
												{columnVisibility.created_by && (
													<TableCell className="w-36 py-2.5 text-sm text-foreground truncate border-r border-border/40">
														{doc.created_by_name ? (
															doc.created_by_email ? (
																<Tooltip>
																	<TooltipTrigger asChild>
																		<span className="cursor-default truncate block">
																			{doc.created_by_name}
																		</span>
																	</TooltipTrigger>
																	<TooltipContent side="top" align="start">
																		{doc.created_by_email}
																	</TooltipContent>
																</Tooltip>
															) : (
																<span className="truncate block">{doc.created_by_name}</span>
															)
														) : (
															<span className="truncate block">{doc.created_by_email || "—"}</span>
														)}
													</TableCell>
												)}
												{columnVisibility.created_at && (
													<TableCell className="w-32 py-2.5 text-sm text-foreground border-r border-border/40">
														<Tooltip>
															<TooltipTrigger asChild>
																<span className="cursor-default">
																	{formatRelativeDate(doc.created_at)}
																</span>
															</TooltipTrigger>
															<TooltipContent side="top">
																{formatAbsoluteDate(doc.created_at)}
															</TooltipContent>
														</Tooltip>
													</TableCell>
												)}
												{columnVisibility.status && (
													<TableCell className="w-14 py-2.5 text-center">
														<StatusIndicator status={doc.status} />
													</TableCell>
												)}
												<TableCell className="w-10 py-2.5 text-center">
													<RowActions
														document={doc}
														deleteDocument={deleteDocument}
														searchSpaceId={searchSpaceId}
													/>
												</TableCell>
											</motion.tr>
										);
									})}
								</TableBody>
							</Table>
						</div>
					</div>

					{/* Mobile Card View - Notion Style */}
					<div className="md:hidden divide-y divide-border/40 h-[50vh] overflow-auto">
						{sorted.map((doc, index) => {
							const isSelected = selectedIds.has(doc.id);
							const canSelect = isSelectable(doc);
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
											onCheckedChange={(v) => canSelect && toggleOne(doc.id, !!v)}
											disabled={!canSelect}
											aria-label={canSelect ? "Select row" : "Cannot select while processing"}
											className={`border-foreground data-[state=checked]:bg-primary data-[state=checked]:border-primary ${!canSelect ? "opacity-40 cursor-not-allowed" : ""}`}
										/>
										<div className="flex-1 min-w-0 space-y-1.5">
											<button
												type="button"
												className="text-left text-sm text-foreground hover:text-foreground transition-colors cursor-pointer truncate block w-full bg-transparent border-0 p-0"
												onClick={(e) => {
													// Ctrl (Win/Linux) or Cmd (Mac) + Click opens metadata
													if (e.ctrlKey || e.metaKey) {
														e.preventDefault();
														e.stopPropagation();
														handleViewMetadata(doc);
													} else {
														// Normal click opens document viewer (lazy loads content)
														handleViewDocument(doc);
													}
												}}
												onKeyDown={(e) => {
													// Ctrl/Cmd + Enter opens metadata
													if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
														e.preventDefault();
														handleViewMetadata(doc);
													} else if (e.key === "Enter") {
														// Enter opens document viewer
														handleViewDocument(doc);
													}
												}}
											>
												{doc.title}
											</button>
											<div className="flex flex-wrap items-center gap-2">
												<DocumentTypeChip type={doc.document_type} />
												{columnVisibility.created_by && doc.created_by_name && (
													<span className="text-xs text-foreground">{doc.created_by_name}</span>
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
										<div className="flex items-center gap-2">
											{columnVisibility.status && <StatusIndicator status={doc.status} />}
											<RowActions
												document={doc}
												deleteDocument={deleteDocument}
												searchSpaceId={searchSpaceId}
											/>
										</div>
									</div>
								</motion.div>
							);
						})}
					</div>
				</>
			)}

			{/* Metadata Viewer - opened via Ctrl/Cmd+Click on document title */}
			{/* Lazy loads metadata from API for real-time synced documents */}
			<JsonMetadataViewer
				title={metadataDoc?.title ?? ""}
				metadata={metadataContent}
				loading={metadataLoading}
				open={!!metadataDoc}
				onOpenChange={(open) => {
					if (!open) handleCloseMetadata();
				}}
			/>

			{/* Document Content Viewer - lazy loads content on-demand */}
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
		</motion.div>
	);
}
