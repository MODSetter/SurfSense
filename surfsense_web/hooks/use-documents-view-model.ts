"use client";

import { useDeferredValue, useMemo } from "react";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import {
	buildDocumentsViewModel,
	type DocumentsViewModel,
} from "@/lib/documents/documents-view-model";
import type { DocumentNodeDoc, FolderDisplay } from "@/lib/documents/document-tree-types";

interface UseDocumentsViewModelInput {
	folders: FolderDisplay[];
	documents: DocumentNodeDoc[];
	pinnedDocuments?: DocumentNodeDoc[];
	query: string;
	activeTypes: DocumentTypeEnum[];
	isLoading?: boolean;
}

export function useDocumentsViewModel({
	folders,
	documents,
	pinnedDocuments,
	query,
	activeTypes,
	isLoading,
}: UseDocumentsViewModelInput): DocumentsViewModel {
	const deferredQuery = useDeferredValue(query);

	return useMemo(
		() =>
			buildDocumentsViewModel({
				folders,
				documents,
				pinnedDocuments,
				query: deferredQuery,
				activeTypes,
				isLoading,
			}),
		[folders, documents, pinnedDocuments, deferredQuery, activeTypes, isLoading]
	);
}
