import type { APIRequestContext } from "@playwright/test";
import { getConnector } from "../api/connectors";
import { isDocumentReady, listDocuments } from "../api/documents";

/**
 * Polls the backend until a connector finishes indexing OR the deadline
 * passes. Replaces `waitForTimeout` (which is a Playwright anti-pattern)
 * with deterministic polling on real signals.
 */
export async function waitForIndexingComplete(
	request: APIRequestContext,
	token: string,
	connectorId: number,
	searchSpaceId: number,
	options: { timeoutMs?: number; intervalMs?: number; minDocuments?: number } = {}
): Promise<void> {
	const timeoutMs = options.timeoutMs ?? 60_000;
	const intervalMs = options.intervalMs ?? 1_000;
	const minDocuments = options.minDocuments ?? 1;

	const startedAt = Date.now();
	let lastState = "unknown";

	while (Date.now() - startedAt < timeoutMs) {
		const connector = await getConnector(request, token, connectorId);
		const docs = await listDocuments(request, token, searchSpaceId);
		const readyDocs = docs.filter(isDocumentReady);

		const connectorIndexed = connector.last_indexed_at !== null;
		const enoughReady = readyDocs.length >= minDocuments;

		if (connectorIndexed && enoughReady) {
			return;
		}

		lastState = `last_indexed_at=${connector.last_indexed_at} ready_docs=${readyDocs.length}/${minDocuments}`;
		await new Promise((resolve) => setTimeout(resolve, intervalMs));
	}

	throw new Error(
		`waitForIndexingComplete: timed out after ${timeoutMs}ms waiting for ` +
			`connector ${connectorId} in space ${searchSpaceId}. Last observed: ${lastState}`
	);
}

/**
 * Polls until the given document title appears in the search space with
 * status=ready. Useful when a spec wants to assert on a specific file
 * by name rather than count.
 */
export async function waitForDocumentByTitle(
	request: APIRequestContext,
	token: string,
	searchSpaceId: number,
	title: string,
	options: { timeoutMs?: number; intervalMs?: number } = {}
): Promise<void> {
	const timeoutMs = options.timeoutMs ?? 60_000;
	const intervalMs = options.intervalMs ?? 1_000;
	const startedAt = Date.now();

	while (Date.now() - startedAt < timeoutMs) {
		const docs = await listDocuments(request, token, searchSpaceId);
		const match = docs.find((d) => d.title === title && isDocumentReady(d));
		if (match) {
			return;
		}
		await new Promise((resolve) => setTimeout(resolve, intervalMs));
	}

	throw new Error(
		`waitForDocumentByTitle: timed out after ${timeoutMs}ms waiting for ` +
			`title=${JSON.stringify(title)} in space ${searchSpaceId}.`
	);
}
