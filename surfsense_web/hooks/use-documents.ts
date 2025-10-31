"use client";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { normalizeListResponse } from "@/lib/pagination";

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
	| "AIRTABLE_CONNECTOR"
	| "LUMA_CONNECTOR"
	| "ELASTICSEARCH_CONNECTOR";

export interface UseDocumentsOptions {
	page?: number;
	pageSize?: number;
	lazy?: boolean;
	documentTypes?: string[];
}

export function useDocuments(searchSpaceId: number, options?: UseDocumentsOptions | boolean) {
	// Support both old boolean API and new options API for backward compatibility
	const opts = typeof options === "boolean" ? { lazy: options } : options || {};
	const { page, pageSize = 300, lazy = false, documentTypes } = opts;

	const [documents, setDocuments] = useState<Document[]>([]);
	const [total, setTotal] = useState(0);
	const [loading, setLoading] = useState(!lazy); // Don't show loading initially for lazy mode
	const [error, setError] = useState<string | null>(null);
	const [isLoaded, setIsLoaded] = useState(false); // Memoization flag

	const fetchDocuments = useCallback(
		async (fetchPage?: number, fetchPageSize?: number, fetchDocumentTypes?: string[]) => {
			if (isLoaded && lazy) return; // Avoid redundant calls in lazy mode

			try {
				setLoading(true);

				// Build query params
				const params = new URLSearchParams({
					search_space_id: searchSpaceId.toString(),
				});

				// Use passed parameters or fall back to state/options
				const effectivePage = fetchPage !== undefined ? fetchPage : page;
				const effectivePageSize = fetchPageSize !== undefined ? fetchPageSize : pageSize;
				const effectiveDocumentTypes =
					fetchDocumentTypes !== undefined ? fetchDocumentTypes : documentTypes;

				if (effectivePage !== undefined) {
					params.append("page", effectivePage.toString());
				}
				if (effectivePageSize !== undefined) {
					params.append("page_size", effectivePageSize.toString());
				}
				if (effectiveDocumentTypes && effectiveDocumentTypes.length > 0) {
					params.append("document_types", effectiveDocumentTypes.join(","));
				}

				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents?${params.toString()}`,
					{
						headers: {
							Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						},
						method: "GET",
					}
				);

				if (!response.ok) {
					toast.error("Failed to fetch documents");
					throw new Error("Failed to fetch documents");
				}

				const data = await response.json();
				const normalized = normalizeListResponse<Document>(data);
				setDocuments(normalized.items);
				setTotal(normalized.total);
				setError(null);
				setIsLoaded(true);
			} catch (err: any) {
				setError(err.message || "Failed to fetch documents");
				console.error("Error fetching documents:", err);
			} finally {
				setLoading(false);
			}
		},
		[searchSpaceId, page, pageSize, documentTypes, isLoaded, lazy]
	);

	useEffect(() => {
		if (!lazy && searchSpaceId) {
			fetchDocuments();
		}
	}, [searchSpaceId, lazy, fetchDocuments]);

	// Function to refresh the documents list
	const refreshDocuments = useCallback(async () => {
		setIsLoaded(false); // Reset memoization flag to allow refetch
		await fetchDocuments();
	}, [fetchDocuments]);

	// Function to search documents by title
	const searchDocuments = useCallback(
		async (
			searchQuery: string,
			fetchPage?: number,
			fetchPageSize?: number,
			fetchDocumentTypes?: string[]
		) => {
			if (!searchQuery.trim()) {
				// If search is empty, fetch all documents
				return fetchDocuments(fetchPage, fetchPageSize, fetchDocumentTypes);
			}

			try {
				setLoading(true);

				// Build query params
				const params = new URLSearchParams({
					search_space_id: searchSpaceId.toString(),
					title: searchQuery,
				});

				// Use passed parameters or fall back to state/options
				const effectivePage = fetchPage !== undefined ? fetchPage : page;
				const effectivePageSize = fetchPageSize !== undefined ? fetchPageSize : pageSize;
				const effectiveDocumentTypes =
					fetchDocumentTypes !== undefined ? fetchDocumentTypes : documentTypes;

				if (effectivePage !== undefined) {
					params.append("page", effectivePage.toString());
				}
				if (effectivePageSize !== undefined) {
					params.append("page_size", effectivePageSize.toString());
				}
				if (effectiveDocumentTypes && effectiveDocumentTypes.length > 0) {
					params.append("document_types", effectiveDocumentTypes.join(","));
				}

				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/search?${params.toString()}`,
					{
						headers: {
							Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						},
						method: "GET",
					}
				);

				if (!response.ok) {
					toast.error("Failed to search documents");
					throw new Error("Failed to search documents");
				}

				const data = await response.json();
				const normalized = normalizeListResponse<Document>(data);
				setDocuments(normalized.items);
				setTotal(normalized.total);
				setError(null);
			} catch (err: any) {
				setError(err.message || "Failed to search documents");
				console.error("Error searching documents:", err);
			} finally {
				setLoading(false);
			}
		},
		[searchSpaceId, page, pageSize, documentTypes, fetchDocuments]
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

	// Function to get document type counts
	const getDocumentTypeCounts = useCallback(async () => {
		try {
			const params = new URLSearchParams({
				search_space_id: searchSpaceId.toString(),
			});

			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/type-counts?${params.toString()}`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					method: "GET",
				}
			);

			if (!response.ok) {
				throw new Error("Failed to fetch document type counts");
			}

			const counts = await response.json();
			return counts as Record<string, number>;
		} catch (err: any) {
			console.error("Error fetching document type counts:", err);
			return {};
		}
	}, [searchSpaceId]);

	return {
		documents,
		total,
		loading,
		error,
		isLoaded,
		fetchDocuments, // Manual fetch function for lazy mode
		searchDocuments, // Search function
		refreshDocuments,
		deleteDocument,
		getDocumentTypeCounts, // Get type counts function
	};
}
