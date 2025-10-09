"use client";
import { useCallback, useState } from "react";
import { toast } from "sonner";

export interface Chunk {
	id: number;
	content: string;
	document_id: number;
	created_at: string;
}

export interface DocumentWithChunks {
	id: number;
	title: string;
	document_type: DocumentType;
	document_metadata: any;
	content: string;
	created_at: string;
	search_space_id: number;
	chunks: Chunk[];
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
	| "LUMA_CONNECTOR"
	| "ELASTICSEARCH_CONNECTOR";

export function useDocumentByChunk() {
	const [document, setDocument] = useState<DocumentWithChunks | null>(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const fetchDocumentByChunk = useCallback(async (chunkId: number) => {
		try {
			setLoading(true);
			setError(null);
			setDocument(null);

			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/by-chunk/${chunkId}`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						"Content-Type": "application/json",
					},
					method: "GET",
				}
			);

			if (!response.ok) {
				const errorText = await response.text();
				let errorMessage = "Failed to fetch document";

				try {
					const errorData = JSON.parse(errorText);
					errorMessage = errorData.detail || errorMessage;
				} catch {
					// If parsing fails, use default message
				}

				if (response.status === 404) {
					errorMessage = "Chunk not found or you don't have access to it";
				}

				toast.error(errorMessage);
				throw new Error(errorMessage);
			}

			const data: DocumentWithChunks = await response.json();
			setDocument(data);
			setError(null);
			return data;
		} catch (err: any) {
			const errorMessage = err.message || "Failed to fetch document";
			setError(errorMessage);
			console.error("Error fetching document by chunk:", err);
			throw err;
		} finally {
			setLoading(false);
		}
	}, []);

	const clearDocument = useCallback(() => {
		setDocument(null);
		setError(null);
	}, []);

	return {
		document,
		loading,
		error,
		fetchDocumentByChunk,
		clearDocument,
	};
}
