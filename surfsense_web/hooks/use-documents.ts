"use client";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { authenticatedFetch } from "@/lib/auth-utils";

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

	const [error, setError] = useState<string | null>(null);

	// Function to delete a document
	const deleteDocument = useCallback(
		async (documentId: number) => {
			try {
				const response = await authenticatedFetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/${documentId}`,
					{ method: "DELETE" }
				);

				if (!response.ok) {
					toast.error("Failed to delete document");
					throw new Error("Failed to delete document");
				}

				toast.success("Document deleted successfully");
			// Note: The caller should handle refetching the documents list
			return true;
		} catch (err: any) {
			toast.error(err.message || "Failed to delete document");
			console.error("Error deleting document:", err);
			return false;
		}
		},
		[]
	);

	return {
		error,
		deleteDocument,
	};
}
