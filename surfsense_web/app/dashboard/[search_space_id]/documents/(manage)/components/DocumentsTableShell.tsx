"use client";

import { ChevronDown, ChevronUp, FileX, Plus } from "lucide-react";
import { motion } from "motion/react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import React, { useState } from "react";
import { useDocumentUploadDialog } from "@/components/assistant-ui/document-upload-popup";
import { DocumentViewer } from "@/components/document-viewer";
import { JsonMetadataViewer } from "@/components/json-metadata-viewer";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { DocumentTypeChip } from "./DocumentTypeIcon";
import { RowActions } from "./RowActions";
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

function formatDate(dateStr: string): string {
	const date = new Date(dateStr);
	return date.toLocaleDateString("en-US", {
		year: "numeric",
		month: "long",
		day: "numeric",
	});
}

function SortableHeader({
	children,
	sortKey,
	currentSortKey,
	sortDesc,
	onSort,
}: {
	children: React.ReactNode;
	sortKey: SortKey;
	currentSortKey: SortKey;
	sortDesc: boolean;
	onSort: (key: SortKey) => void;
}) {
	const isActive = currentSortKey === sortKey;
	return (
		<button
			type="button"
			onClick={() => onSort(sortKey)}
			className="flex items-center gap-1.5 text-left font-medium text-muted-foreground hover:text-foreground transition-colors group"
		>
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
	deleteDocument,
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
	deleteDocument: (id: number) => Promise<boolean>;
	sortKey: SortKey;
	sortDesc: boolean;
	onSortChange: (key: SortKey) => void;
}) {
	const t = useTranslations("documents");
	const params = useParams();
	const searchSpaceId = params.search_space_id;
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
			className="rounded-xl border border-border/50 bg-card/30 backdrop-blur-sm overflow-hidden shadow-sm"
			initial={{ opacity: 0, y: 20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ type: "spring", stiffness: 300, damping: 30, delay: 0.2 }}
		>
			{loading ? (
				<div className="flex h-[400px] w-full items-center justify-center">
					<div className="flex flex-col items-center gap-3">
						<Spinner size="lg" className="text-primary" />
						<p className="text-sm text-muted-foreground">{t("loading")}</p>
					</div>
				</div>
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
					{/* Desktop Table View */}
					<div className="hidden md:flex md:flex-col">
						{/* Fixed Header */}
						<Table>
							<TableHeader>
								<TableRow className="bg-muted/30 hover:bg-muted/30 border-b border-border/50">
									<TableHead className="w-[40px] pl-4">
										<Checkbox
											checked={allSelectedOnPage || (someSelectedOnPage && "indeterminate")}
											onCheckedChange={(v) => toggleAll(!!v)}
											aria-label="Select all"
											className="data-[state=checked]:bg-primary data-[state=checked]:border-primary"
										/>
									</TableHead>
									<TableHead className="min-w-[200px]">
										<SortableHeader
											sortKey="title"
											currentSortKey={sortKey}
											sortDesc={sortDesc}
											onSort={onSortHeader}
										>
											Document
										</SortableHeader>
									</TableHead>
									{columnVisibility.document_type && (
										<TableHead className="w-[160px]">
											<SortableHeader
												sortKey="document_type"
												currentSortKey={sortKey}
												sortDesc={sortDesc}
												onSort={onSortHeader}
											>
												Source
											</SortableHeader>
										</TableHead>
									)}
									{columnVisibility.created_by && (
										<TableHead className="w-[150px]">
											<span className="text-muted-foreground font-medium">User</span>
										</TableHead>
									)}
									{columnVisibility.created_at && (
										<TableHead className="w-[150px]">
											<SortableHeader
												sortKey="created_at"
												currentSortKey={sortKey}
												sortDesc={sortDesc}
												onSort={onSortHeader}
											>
												Created
											</SortableHeader>
										</TableHead>
									)}
									<TableHead className="w-[80px] pr-4">
										<span className="sr-only">Actions</span>
									</TableHead>
								</TableRow>
							</TableHeader>
						</Table>
						{/* Scrollable Body */}
						<div className="max-h-[55vh] overflow-auto">
							<Table>
								<TableBody>
									{sorted.map((doc, index) => {
										const title = doc.title;
										const truncatedTitle = title.length > 50 ? `${title.slice(0, 50)}...` : title;
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
														? "bg-primary/5 hover:bg-primary/10"
														: "hover:bg-muted/40"
												}`}
											>
												<TableCell className="w-[40px] pl-4 py-3">
													<Checkbox
														checked={isSelected}
														onCheckedChange={(v) => toggleOne(doc.id, !!v)}
														aria-label="Select row"
														className="data-[state=checked]:bg-primary data-[state=checked]:border-primary"
													/>
												</TableCell>
												<TableCell className="min-w-[200px] py-3">
													<DocumentViewer
														title={doc.title}
														content={doc.content}
														trigger={
															<button
																type="button"
																className="text-left font-medium text-foreground/90 hover:text-primary transition-colors cursor-pointer bg-transparent border-0 p-0"
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
																{title.length > 50 ? (
																	<Tooltip>
																		<TooltipTrigger asChild>
																			<span>{truncatedTitle}</span>
																		</TooltipTrigger>
																		<TooltipContent side="top" className="max-w-xs">
																			<p className="break-words">{title}</p>
																		</TooltipContent>
																	</Tooltip>
																) : (
																	title
																)}
															</button>
														}
													/>
												</TableCell>
												{columnVisibility.document_type && (
													<TableCell className="w-[160px] py-3">
														<DocumentTypeChip type={doc.document_type} />
													</TableCell>
												)}
												{columnVisibility.created_by && (
													<TableCell className="w-[150px] py-3 text-sm text-muted-foreground truncate">
														{doc.created_by_name || "—"}
													</TableCell>
												)}
												{columnVisibility.created_at && (
													<TableCell className="w-[150px] py-3 text-sm text-muted-foreground">
														{formatDate(doc.created_at)}
													</TableCell>
												)}
												<TableCell className="w-[80px] pr-4 py-3">
													<RowActions
														document={doc}
														deleteDocument={deleteDocument}
														refreshDocuments={async () => {
															await onRefresh();
														}}
														searchSpaceId={searchSpaceId as string}
													/>
												</TableCell>
											</motion.tr>
										);
									})}
								</TableBody>
							</Table>
						</div>
					</div>

					{/* Mobile Card View */}
					<div className="md:hidden divide-y divide-border/30">
						{sorted.map((doc, index) => {
							const isSelected = selectedIds.has(doc.id);
							return (
								<motion.div
									key={doc.id}
									initial={{ opacity: 0 }}
									animate={{ opacity: 1, transition: { delay: index * 0.03 } }}
									className={`p-4 transition-colors ${
										isSelected ? "bg-primary/5" : "hover:bg-muted/30"
									}`}
								>
									<div className="flex items-start gap-3">
										<Checkbox
											checked={isSelected}
											onCheckedChange={(v) => toggleOne(doc.id, !!v)}
											aria-label="Select row"
											className="mt-0.5 data-[state=checked]:bg-primary data-[state=checked]:border-primary"
										/>
										<div className="flex-1 min-w-0 space-y-2">
											<DocumentViewer
												title={doc.title}
												content={doc.content}
												trigger={
													<button
														type="button"
														className="text-left font-medium text-sm text-foreground/90 hover:text-primary transition-colors cursor-pointer truncate block w-full bg-transparent border-0 p-0"
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
													<span className="text-xs text-muted-foreground">
														{doc.created_by_name}
													</span>
												)}
												{columnVisibility.created_at && (
													<span className="text-xs text-muted-foreground">
														{formatDate(doc.created_at)}
													</span>
												)}
											</div>
										</div>
										<RowActions
											document={doc}
											deleteDocument={deleteDocument}
											refreshDocuments={async () => {
												await onRefresh();
											}}
											searchSpaceId={searchSpaceId as string}
										/>
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
