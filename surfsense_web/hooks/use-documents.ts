"use client";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

export interface Document {
	id: number;
	title: string;
	document_type: DocumentType;
	document_metadata: any;
	content: string;
	created_at: string;
	search_space_id: number;
}

export type DocumentType =
	| "EXTENSION"
	| "CRAWLED_URL"
	| "SLACK_CONNECTOR"
	| "NOTION_CONNECTOR"
	| "FILE"
	| "YOUTUBE_VIDEO"
	| "GITHUB_CONNECTOR"
	| "LINEAR_CONNECTOR"
	| "DISCORD_CONNECTOR"
	| "JIRA_CONNECTOR"
	| "CONFLUENCE_CONNECTOR"
	| "CLICKUP_CONNECTOR"
	| "GOOGLE_CALENDAR_CONNECTOR"
	| "GOOGLE_GMAIL_CONNECTOR"
	| "AIRTABLE_CONNECTOR";

export function useDocuments(
	searchSpaceId: number,
	optionsOrLazy?: boolean | { pageIndex?: number; pageSize?: number; lazy?: boolean }
) {
	const lazy = typeof optionsOrLazy === "boolean" ? optionsOrLazy : (optionsOrLazy?.lazy ?? false);
	const pageIndex =
		typeof optionsOrLazy === "object" && optionsOrLazy?.pageIndex !== undefined
			? optionsOrLazy.pageIndex
			: 0;
	const pageSize =
		typeof optionsOrLazy === "object" && optionsOrLazy?.pageSize !== undefined
			? optionsOrLazy.pageSize
			: 50;

	const [documents, setDocuments] = useState<Document[]>([]);
	const [loading, setLoading] = useState(!lazy);
	const [error, setError] = useState<string | null>(null);
	const [isLoaded, setIsLoaded] = useState(false);
	const [hasMore, setHasMore] = useState(false);

	const fetchDocuments = useCallback(
		async (override?: { pageIndex?: number; pageSize?: number }) => {
			if (isLoaded && lazy && !override) return;

			const effectivePageIndex = override?.pageIndex ?? pageIndex;
			const effectivePageSize = override?.pageSize ?? pageSize;
			const skip = effectivePageIndex * effectivePageSize;
			const limit = effectivePageSize;

			try {
				setLoading(true);
				const url = new URL(`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents`);
				if (searchSpaceId) url.searchParams.set("search_space_id", String(searchSpaceId));
				url.searchParams.set("skip", String(skip));
				url.searchParams.set("limit", String(limit));

				const response = await fetch(url.toString(), {
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					method: "GET",
				});

				if (!response.ok) {
					toast.error("Failed to fetch documents");
					throw new Error("Failed to fetch documents");
				}

				const data = await response.json();
				setDocuments(data);
				setHasMore(Array.isArray(data) && data.length === effectivePageSize);
				setError(null);
				setIsLoaded(true);
			} catch (err: any) {
				setError(err.message || "Failed to fetch documents");
				console.error("Error fetching documents:", err);
			} finally {
				setLoading(false);
			}
		},
		[searchSpaceId, isLoaded, lazy, pageIndex, pageSize]
	);

	useEffect(() => {
		if (!lazy && searchSpaceId !== undefined && searchSpaceId !== null) {
			fetchDocuments();
		}
	}, [searchSpaceId, lazy, fetchDocuments]);

	const refreshDocuments = useCallback(
		async (override?: { pageIndex?: number; pageSize?: number }) => {
			setIsLoaded(false);
			await fetchDocuments(override);
		},
		[fetchDocuments]
	);

	// Function to delete a document
	const deleteDocument = useCallback(
		async (documentId: number) => {
			try {
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/${documentId}`,
					{
						headers: {
							Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						},
						method: "DELETE",
					}
				);

				if (!response.ok) {
					toast.error("Failed to delete document");
					throw new Error("Failed to delete document");
				}

				toast.success("Document deleted successfully");
				// Update the local state after successful deletion
				setDocuments(documents.filter((doc) => doc.id !== documentId));
				return true;
			} catch (err: any) {
				toast.error(err.message || "Failed to delete document");
				console.error("Error deleting document:", err);
				return false;
			}
		},
		[documents]
	);

	return {
		documents,
		loading,
		error,
		isLoaded,
		fetchDocuments, // Manual fetch function for lazy mode
		refreshDocuments,
		deleteDocument,
		hasMore,
		pageIndex,
		pageSize,
	};
}
