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
		`${BACKEND_URL}/api/v1/documents?search_space_id=${searchSpaceId}&limit=${limit}`,
		{ headers: authHeaders(token) }
	);
	if (!response.ok()) {
		throw new Error(
			`listDocuments failed (${response.status()}): ${await response.text()}`
		);
	}
	const body = (await response.json()) as Paginated<DocumentRow> | DocumentRow[];
	return Array.isArray(body) ? body : (body.items ?? []);
}

export function isDocumentReady(doc: DocumentRow): boolean {
	const state =
		typeof doc.status === "string" ? doc.status : doc.status?.state;
	return state === "ready" || state === "READY";
}
