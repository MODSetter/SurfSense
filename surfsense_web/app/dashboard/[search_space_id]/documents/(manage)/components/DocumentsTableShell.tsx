"use client";

import { ChevronDown, ChevronUp, FileX } from "lucide-react";
import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import React from "react";
import { DocumentViewer } from "@/components/document-viewer";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { DocumentTypeChip, getDocumentTypeIcon } from "./DocumentTypeIcon";
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

function truncate(text: string, len = 150): string {
	const plain = text
		.replace(/[#*_`>\-[\]()]+/g, " ")
		.replace(/\s+/g, " ")
		.trim();
	if (plain.length <= len) return plain;
	return `${plain.slice(0, len)}...`;
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
	const sorted = React.useMemo(
		() => sortDocuments(documents, sortKey, sortDesc),
		[documents, sortKey, sortDesc]
	);

	const allSelectedOnPage = sorted.length > 0 && sorted.every((d) => selectedIds.has(d.id));
	const someSelectedOnPage = sorted.some((d) => selectedIds.has(d.id)) && !allSelectedOnPage;

	const toggleAll = (checked: boolean) => {
		const next = new Set(selectedIds);
		if (checked) sorted.forEach((d) => next.add(d.id));
		else sorted.forEach((d) => next.delete(d.id));
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
			className="rounded-md border mt-6 overflow-hidden"
			initial={{ opacity: 0, y: 20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ type: "spring", stiffness: 300, damping: 30, delay: 0.2 }}
		>
			{loading ? (
				<div className="flex h-[400px] w-full items-center justify-center">
					<div className="flex flex-col items-center gap-2">
						<div className="h-8 w-8 animate-spin rounded-full border-b-2 border-primary"></div>
						<p className="text-sm text-muted-foreground">{t("loading")}</p>
					</div>
				</div>
			) : error ? (
				<div className="flex h-[400px] w-full items-center justify-center">
					<div className="flex flex-col items-center gap-2">
						<p className="text-sm text-destructive">{t("error_loading")}</p>
						<Button variant="outline" size="sm" onClick={() => onRefresh()} className="mt-2">
							{t("retry")}
						</Button>
					</div>
				</div>
			) : sorted.length === 0 ? (
				<div className="flex h-[400px] w-full items-center justify-center">
					<div className="flex flex-col items-center gap-2">
						<FileX className="h-8 w-8 text-muted-foreground" />
						<p className="text-sm text-muted-foreground">{t("no_documents")}</p>
					</div>
				</div>
			) : (
				<>
					<div className="hidden md:block max-h-[60vh] overflow-auto">
						<Table className="table-fixed w-full">
							<TableHeader className="sticky top-0 bg-background z-10">
								<TableRow className="hover:bg-transparent">
									<TableHead style={{ width: 28 }}>
										<Checkbox
											checked={allSelectedOnPage || (someSelectedOnPage && "indeterminate")}
											onCheckedChange={(v) => toggleAll(!!v)}
											aria-label="Select all"
										/>
									</TableHead>
									{columnVisibility.title && (
										<TableHead style={{ width: 250 }}>
											<Button
												variant="ghost"
												className="flex h-full w-full cursor-pointer select-none items-center justify-between gap-2"
												onClick={() => onSortHeader("title")}
											>
												{t("title")}
												{sortKey === "title" ? (
													sortDesc ? (
														<ChevronDown className="shrink-0 opacity-60" size={16} />
													) : (
														<ChevronUp className="shrink-0 opacity-60" size={16} />
													)
												) : null}
											</Button>
										</TableHead>
									)}
									{columnVisibility.document_type && (
										<TableHead style={{ width: 180 }}>
											<Button
												variant="ghost"
												className="flex h-full w-full cursor-pointer select-none items-center justify-between gap-2"
												onClick={() => onSortHeader("document_type")}
											>
												{t("type")}
												{sortKey === "document_type" ? (
													sortDesc ? (
														<ChevronDown className="shrink-0 opacity-60" size={16} />
													) : (
														<ChevronUp className="shrink-0 opacity-60" size={16} />
													)
												) : null}
											</Button>
										</TableHead>
									)}
									{columnVisibility.content && (
										<TableHead style={{ width: 300 }}>{t("content_summary")}</TableHead>
									)}
									{columnVisibility.created_at && (
										<TableHead style={{ width: 120 }}>
											<Button
												variant="ghost"
												className="flex h-full w-full cursor-pointer select-none items-center justify-between gap-2"
												onClick={() => onSortHeader("created_at")}
											>
												Created At
												{sortKey === "created_at" ? (
													sortDesc ? (
														<ChevronDown className="shrink-0 opacity-60" size={16} />
													) : (
														<ChevronUp className="shrink-0 opacity-60" size={16} />
													)
												) : null}
											</Button>
										</TableHead>
									)}
									<TableHead style={{ width: 60 }}>
										<span className="sr-only">Actions</span>
									</TableHead>
								</TableRow>
							</TableHeader>
							<TableBody>
								{sorted.map((doc, index) => {
									const icon = getDocumentTypeIcon(doc.document_type);
									const title = doc.title;
									const truncatedTitle = title.length > 30 ? `${title.slice(0, 30)}...` : title;
									return (
										<motion.tr
											key={doc.id}
											initial={{ opacity: 0, y: 10 }}
											animate={{
												opacity: 1,
												y: 0,
												transition: {
													type: "spring",
													stiffness: 300,
													damping: 30,
													delay: index * 0.03,
												},
											}}
											exit={{ opacity: 0, y: -10 }}
											className="border-b transition-colors hover:bg-muted/50"
										>
											<TableCell className="px-4 py-3">
												<Checkbox
													checked={selectedIds.has(doc.id)}
													onCheckedChange={(v) => toggleOne(doc.id, !!v)}
													aria-label="Select row"
												/>
											</TableCell>
											{columnVisibility.title && (
												<TableCell className="px-4 py-3">
													<motion.div
														className="flex items-center gap-2 font-medium"
														whileHover={{ scale: 1.02 }}
														transition={{ type: "spring", stiffness: 300 }}
														style={{ display: "flex" }}
													>
														<Tooltip>
															<TooltipTrigger asChild>
																<span className="flex items-center gap-2">
																	<span className="text-muted-foreground shrink-0">{icon}</span>
																	<span>{truncatedTitle}</span>
																</span>
															</TooltipTrigger>
															<TooltipContent>
																<p>{title}</p>
															</TooltipContent>
														</Tooltip>
													</motion.div>
												</TableCell>
											)}
											{columnVisibility.document_type && (
												<TableCell className="px-4 py-3">
													<div className="flex items-center gap-2">
														<DocumentTypeChip type={doc.document_type} />
													</div>
												</TableCell>
											)}
											{columnVisibility.content && (
												<TableCell className="px-4 py-3">
													<div className="flex flex-col gap-2">
														<div className="max-w-[300px] max-h-[60px] overflow-hidden text-sm text-muted-foreground">
															{truncate(doc.content)}
														</div>
														<DocumentViewer
															title={doc.title}
															content={doc.content}
															trigger={
																<Button variant="ghost" size="sm" className="w-fit text-xs">
																	{t("view_full")}
																</Button>
															}
														/>
													</div>
												</TableCell>
											)}
											{columnVisibility.created_at && (
												<TableCell className="px-4 py-3">
													{new Date(doc.created_at).toLocaleDateString()}
												</TableCell>
											)}
											<TableCell className="px-4 py-3">
												<RowActions
													document={doc}
													deleteDocument={deleteDocument}
													refreshDocuments={async () => {
														await onRefresh();
													}}
												/>
											</TableCell>
										</motion.tr>
									);
								})}
							</TableBody>
						</Table>
					</div>
					<div className="md:hidden divide-y">
						{sorted.map((doc) => {
							const icon = getDocumentTypeIcon(doc.document_type);
							return (
								<div key={doc.id} className="p-3">
									<div className="flex items-start gap-3">
										<Checkbox
											checked={selectedIds.has(doc.id)}
											onCheckedChange={(v) => toggleOne(doc.id, !!v)}
											aria-label="Select row"
										/>
										<div className="flex-1 min-w-0">
											<div className="flex items-center justify-between gap-2">
												<div className="flex items-center gap-2 min-w-0">
													<span className="text-muted-foreground shrink-0">{icon}</span>
													<div className="font-medium truncate">{doc.title}</div>
												</div>
												<RowActions
													document={doc}
													deleteDocument={deleteDocument}
													refreshDocuments={async () => {
														await onRefresh();
													}}
												/>
											</div>
											<div className="mt-1 flex flex-wrap items-center gap-2">
												<DocumentTypeChip type={doc.document_type} />
												<span className="text-xs text-muted-foreground">
													{new Date(doc.created_at).toLocaleDateString()}
												</span>
											</div>
											{columnVisibility.content && (
												<div className="mt-2 text-sm text-muted-foreground">
													{truncate(doc.content)}
													<div className="mt-1">
														<DocumentViewer
															title={doc.title}
															content={doc.content}
															trigger={
																<Button
																	variant="ghost"
																	size="sm"
																	className="w-fit text-xs p-0 h-auto"
																>
																	{t("view_full")}
																</Button>
															}
														/>
													</div>
												</div>
											)}
										</div>
									</div>
								</div>
							);
						})}
					</div>
				</>
			)}
		</motion.div>
	);
}
