import type { APIRequestContext } from "@playwright/test";
import { authHeaders, BACKEND_URL } from "./auth";

export type DocumentRow = {
	id: number;
	title: string;
	content: string;
	document_type: string;
	status: { state?: string } | string;
};

type Paginated<T> = {
	items?: T[];
	total?: number;
};

export async function listDocuments(
	request: APIRequestContext,
	token: string,
	searchSpaceId: number,
	limit = 100
): Promise<DocumentRow[]> {
	const response = await request.get(
		`${BACKEND_URL}/api/v1/documents?workspace_id=${searchSpaceId}&limit=${limit}`,
		{ headers: authHeaders(token) }
	);
	if (!response.ok()) {
		throw new Error(`listDocuments failed (${response.status()}): ${await response.text()}`);
	}
	const body = (await response.json()) as Paginated<DocumentRow> | DocumentRow[];
	return Array.isArray(body) ? body : (body.items ?? []);
}

export function isDocumentReady(doc: DocumentRow): boolean {
	const state = typeof doc.status === "string" ? doc.status : doc.status?.state;
	return state === "ready" || state === "READY";
}

export type EditorContent = {
	document_id: number;
	title: string;
	document_type: string;
	source_markdown: string;
	content_size_bytes: number;
	chunk_count: number;
	viewer_mode?: "plate" | "monaco";
	editor_plate_max_bytes?: number;
};

// Same endpoint the UI hits when a user opens a document in the dashboard.
export async function getEditorContent(
	request: APIRequestContext,
	token: string,
	searchSpaceId: number,
	documentId: number
): Promise<EditorContent> {
	const response = await request.get(
		`${BACKEND_URL}/api/v1/search-spaces/${searchSpaceId}/documents/${documentId}/editor-content`,
		{ headers: authHeaders(token) }
	);
	if (!response.ok()) {
		throw new Error(`getEditorContent failed (${response.status()}): ${await response.text()}`);
	}
	return (await response.json()) as EditorContent;
}
