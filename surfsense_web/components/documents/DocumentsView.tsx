"use client";

import type { FolderDisplay } from "@/lib/documents/document-tree-types";
import type { DocumentsViewModel } from "@/lib/documents/documents-view-model";
import { DocumentsEmptyState } from "./DocumentsEmptyState";
import { DocumentsSearchResults } from "./DocumentsSearchResults";
import { FolderTreeView, type FolderTreeViewProps } from "./FolderTreeView";

interface DocumentsViewProps extends Omit<FolderTreeViewProps, "folders" | "documents"> {
	viewModel: DocumentsViewModel;
	onOpenFolder: (folder: FolderDisplay) => void;
}

export function DocumentsView({ viewModel, onOpenFolder, ...treeProps }: DocumentsViewProps) {
	if (viewModel.mode === "empty") {
		return <DocumentsEmptyState reason={viewModel.reason} />;
	}

	if (viewModel.mode === "search") {
		return (
			<DocumentsSearchResults
				hits={viewModel.hits}
				onOpenDocument={treeProps.onPreviewDocument}
				onOpenFolder={onOpenFolder}
			/>
		);
	}

	return (
		<FolderTreeView {...treeProps} folders={viewModel.folders} documents={viewModel.documents} />
	);
}
