"use client";

import { CircleAlert, Dot, Folder, LoaderCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import type { DocumentNodeDoc, FolderDisplay } from "@/lib/documents/document-tree-types";
import { getDocumentTypeLabel } from "@/lib/documents/document-type-labels";
import type { DocumentSearchHit } from "@/lib/documents/documents-view-model";
import { getDocumentTypeIcon } from "./DocumentTypeIcon";
import { HighlightedText } from "./HighlightedText";

interface DocumentsSearchResultsProps {
	hits: DocumentSearchHit[];
	onOpenDocument: (document: DocumentNodeDoc) => void;
	onOpenFolder: (folder: FolderDisplay) => void;
}

export function DocumentsSearchResults({
	hits,
	onOpenDocument,
	onOpenFolder,
}: DocumentsSearchResultsProps) {
	const t = useTranslations("documents");

	return (
		<div className="px-2 py-1">
			<output className="block px-2 pb-1.5 text-[11px] font-medium text-muted-foreground">
				{t("search_results", { count: hits.length })}
			</output>
			<ul aria-label={t("search_results_label")}>
				{hits.map((hit) => {
					const title = hit.kind === "document" ? hit.document.title : hit.folder.name;
					const path = hit.path.length > 0 ? hit.path.join(" / ") : t("search_root");
					const isProcessing =
						hit.kind === "document" &&
						(hit.document.status?.state === "pending" ||
							hit.document.status?.state === "processing");
					const isUnavailable =
						isProcessing || (hit.kind === "document" && hit.document.status?.state === "failed");
					const isFailed = hit.kind === "document" && hit.document.status?.state === "failed";

					return (
						<li key={`${hit.kind}-${hit.kind === "document" ? hit.document.id : hit.folder.id}`}>
							<button
								type="button"
								disabled={isUnavailable}
								onClick={() =>
									hit.kind === "document" ? onOpenDocument(hit.document) : onOpenFolder(hit.folder)
								}
								className="group flex w-full items-center gap-2 rounded-md px-2 py-2 text-left transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
							>
								<span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
									{isProcessing ? (
										<span className="animate-spin">
											<LoaderCircle className="size-4" />
										</span>
									) : isFailed ? (
										<CircleAlert className="size-4 text-destructive" />
									) : hit.kind === "document" ? (
										getDocumentTypeIcon(hit.document.document_type, "size-4")
									) : (
										<Folder className="size-4" />
									)}
								</span>
								<span className="min-w-0 flex-1">
									<span className="block truncate text-sm font-medium">
										<HighlightedText text={title} ranges={hit.match.ranges} />
									</span>
									<span className="flex items-center text-[11px] text-muted-foreground">
										{isFailed ? (
											(hit.kind === "document" && hit.document.status?.reason) ||
											t("search_document_failed")
										) : (
											<>
												<span className="truncate">{path}</span>
												<Dot className="size-3 shrink-0" aria-hidden="true" />
												<span className="shrink-0">
													{hit.kind === "document"
														? getDocumentTypeLabel(hit.document.document_type)
														: t("search_folder")}
												</span>
											</>
										)}
									</span>
								</span>
							</button>
						</li>
					);
				})}
			</ul>
		</div>
	);
}
