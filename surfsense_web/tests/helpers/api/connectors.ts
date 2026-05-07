import type { APIRequestContext } from "@playwright/test";
import { authHeaders, BACKEND_URL } from "./auth";

export type ConnectorRow = {
	id: number;
	name: string;
	connector_type: string;
	config: Record<string, unknown>;
	last_indexed_at: string | null;
	is_indexable: boolean;
};

export async function listConnectors(
	request: APIRequestContext,
	token: string,
	searchSpaceId: number
): Promise<ConnectorRow[]> {
	const response = await request.get(
		`${BACKEND_URL}/api/v1/search-source-connectors?search_space_id=${searchSpaceId}`,
		{ headers: authHeaders(token) }
	);
	if (!response.ok()) {
		throw new Error(`listConnectors failed (${response.status()}): ${await response.text()}`);
	}
	const data = await response.json();
	return Array.isArray(data) ? data : (data?.items ?? []);
}

export async function getConnector(
	request: APIRequestContext,
	token: string,
	connectorId: number
): Promise<ConnectorRow> {
	const response = await request.get(
		`${BACKEND_URL}/api/v1/search-source-connectors/${connectorId}`,
		{ headers: authHeaders(token) }
	);
	if (!response.ok()) {
		throw new Error(
			`getConnector(${connectorId}) failed (${response.status()}): ${await response.text()}`
		);
	}
	return (await response.json()) as ConnectorRow;
}

export async function updateConnectorConfig(
	request: APIRequestContext,
	token: string,
	connectorId: number,
	config: Record<string, unknown>
): Promise<ConnectorRow> {
	const response = await request.put(
		`${BACKEND_URL}/api/v1/search-source-connectors/${connectorId}`,
		{ headers: authHeaders(token), data: { config } }
	);
	if (!response.ok()) {
		throw new Error(
			`updateConnectorConfig(${connectorId}) failed (${response.status()}): ${await response.text()}`
		);
	}
	return (await response.json()) as ConnectorRow;
}

export async function deleteConnector(
	request: APIRequestContext,
	token: string,
	connectorId: number
): Promise<void> {
	const response = await request.delete(
		`${BACKEND_URL}/api/v1/search-source-connectors/${connectorId}`,
		{ headers: authHeaders(token) }
	);
	if (!response.ok() && response.status() !== 404) {
		throw new Error(
			`deleteConnector(${connectorId}) failed (${response.status()}): ${await response.text()}`
		);
	}
}

export async function listComposioDriveFolders(
	request: APIRequestContext,
	token: string,
	connectorId: number,
	parentId?: string
): Promise<{ items: Array<Record<string, unknown>> }> {
	const url = parentId
		? `${BACKEND_URL}/api/v1/connectors/${connectorId}/composio-drive/folders?parent_id=${encodeURIComponent(parentId)}`
		: `${BACKEND_URL}/api/v1/connectors/${connectorId}/composio-drive/folders`;
	const response = await request.get(url, {
		headers: authHeaders(token),
	});
	if (!response.ok()) {
		throw new Error(
			`listComposioDriveFolders(${connectorId}) failed (${response.status()}): ${await response.text()}`
		);
	}
	return (await response.json()) as { items: Array<Record<string, unknown>> };
}

export type IndexBody = {
	folders?: Array<{ id: string; name: string; mimeType: string }>;
	files?: Array<{ id: string; name: string; mimeType: string }>;
	indexing_options?: {
		max_files_per_folder?: number;
		incremental_sync?: boolean;
		include_subfolders?: boolean;
	};
};

export async function triggerIndex(
	request: APIRequestContext,
	token: string,
	connectorId: number,
	searchSpaceId: number,
	body: IndexBody
): Promise<{ ok: true }> {
	const response = await request.post(
		`${BACKEND_URL}/api/v1/search-source-connectors/${connectorId}/index?search_space_id=${searchSpaceId}`,
		{ headers: authHeaders(token), data: body }
	);
	if (!response.ok()) {
		throw new Error(
			`triggerIndex(${connectorId}) failed (${response.status()}): ${await response.text()}`
		);
	}
	return { ok: true };
}

export async function triggerIndexExpectDisabled(
	request: APIRequestContext,
	token: string,
	connectorId: number,
	searchSpaceId: number,
	body: IndexBody = {}
): Promise<{ indexing_started: false; message?: string }> {
	const response = await request.post(
		`${BACKEND_URL}/api/v1/search-source-connectors/${connectorId}/index?search_space_id=${searchSpaceId}`,
		{ headers: authHeaders(token), data: body }
	);
	if (!response.ok()) {
		throw new Error(
			`triggerIndexExpectDisabled(${connectorId}) failed (${response.status()}): ${await response.text()}`
		);
	}
	const payload = (await response.json()) as { indexing_started?: boolean; message?: string };
	if (payload.indexing_started !== false) {
		throw new Error(
			`triggerIndexExpectDisabled(${connectorId}) expected indexing_started=false, got ${JSON.stringify(payload)}`
		);
	}
	return { indexing_started: false, message: payload.message };
}

/**
 * Drives the OAuth flow for a Composio toolkit programmatically.
 *
 * Steps mirror what the UI does (see use-connector-dialog.ts):
 *   1) GET /api/v1/auth/composio/connector/add?space_id=&toolkit_id=  -> { auth_url }
 *   2) Follow the auth_url (which the E2E fake makes same-origin so it
 *      lands on the callback directly with ?connectedAccountId=...).
 *   3) Backend creates the connector and redirects to the frontend
 *      success page.
 *
 * Returns the newly-created (or reconnected) connector row.
 */
export async function runComposioOAuth(
	request: APIRequestContext,
	token: string,
	searchSpaceId: number,
	toolkitId: "googledrive" | "gmail" | "googlecalendar" = "googledrive"
): Promise<{
	authUrl: string;
	finalUrl: string;
	connector: ConnectorRow | null;
}> {
	// Step 1: kick off OAuth, get auth_url.
	const initiateResp = await request.get(
		`${BACKEND_URL}/api/v1/auth/composio/connector/add?space_id=${searchSpaceId}&toolkit_id=${toolkitId}`,
		{
			headers: authHeaders(token),
		}
	);
	if (!initiateResp.ok()) {
		throw new Error(
			`composio initiate failed (${initiateResp.status()}): ${await initiateResp.text()}`
		);
	}
	const { auth_url } = (await initiateResp.json()) as { auth_url: string };
	if (!auth_url) {
		throw new Error("composio initiate response missing auth_url");
	}

	// Step 2: follow the auth_url. The fake makes this same-origin and
	// pointing at the callback. Use maxRedirects=0 so we can inspect
	// the final redirect target manually.
	const callbackResp = await request.get(auth_url, {
		headers: authHeaders(token),
		maxRedirects: 0,
		failOnStatusCode: false,
	});

	const location = callbackResp.headers().location ?? auth_url;

	// Step 3: look up the resulting connector (if any).
	const connectors = await listConnectors(request, token, searchSpaceId);
	const composioType =
		toolkitId === "googledrive"
			? "COMPOSIO_GOOGLE_DRIVE_CONNECTOR"
			: toolkitId === "gmail"
				? "COMPOSIO_GMAIL_CONNECTOR"
				: "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR";
	const connector = connectors.find((c) => c.connector_type === composioType) ?? null;

	return { authUrl: auth_url, finalUrl: location, connector };
}

/**
 * Drives the native Google Drive OAuth flow programmatically.
 *
 * The E2E backend patches Google OAuth so the returned auth_url points
 * straight back to the backend callback with a deterministic code/state.
 */
export async function runNativeGoogleDriveOAuth(
	request: APIRequestContext,
	token: string,
	searchSpaceId: number
): Promise<{
	authUrl: string;
	finalUrl: string;
	connector: ConnectorRow | null;
}> {
	const initiateResp = await request.get(
		`${BACKEND_URL}/api/v1/auth/google/drive/connector/add?space_id=${searchSpaceId}`,
		{ headers: authHeaders(token) }
	);
	if (!initiateResp.ok()) {
		throw new Error(
			`native Google Drive initiate failed (${initiateResp.status()}): ${await initiateResp.text()}`
		);
	}
	const { auth_url } = (await initiateResp.json()) as { auth_url: string };
	if (!auth_url) {
		throw new Error("native Google Drive initiate response missing auth_url");
	}

	const callbackResp = await request.get(auth_url, {
		headers: authHeaders(token),
		maxRedirects: 0,
		failOnStatusCode: false,
	});
	const location = callbackResp.headers().location ?? auth_url;

	const connectors = await listConnectors(request, token, searchSpaceId);
	const connector = connectors.find((c) => c.connector_type === "GOOGLE_DRIVE_CONNECTOR") ?? null;

	return { authUrl: auth_url, finalUrl: location, connector };
}

/**
 * Drives the native Google Gmail OAuth flow programmatically.
 *
 * The E2E backend patches Google OAuth so the returned auth_url points
 * straight back to the backend callback with a deterministic code/state.
 */
export async function runNativeGoogleGmailOAuth(
	request: APIRequestContext,
	token: string,
	searchSpaceId: number
): Promise<{
	authUrl: string;
	finalUrl: string;
	connector: ConnectorRow | null;
}> {
	const initiateResp = await request.get(
		`${BACKEND_URL}/api/v1/auth/google/gmail/connector/add?space_id=${searchSpaceId}`,
		{ headers: authHeaders(token) }
	);
	if (!initiateResp.ok()) {
		throw new Error(
			`native Google Gmail initiate failed (${initiateResp.status()}): ${await initiateResp.text()}`
		);
	}
	const { auth_url } = (await initiateResp.json()) as { auth_url: string };
	if (!auth_url) {
		throw new Error("native Google Gmail initiate response missing auth_url");
	}

	const callbackResp = await request.get(auth_url, {
		headers: authHeaders(token),
		maxRedirects: 0,
		failOnStatusCode: false,
	});
	const location = callbackResp.headers().location ?? auth_url;

	const connectors = await listConnectors(request, token, searchSpaceId);
	const connector = connectors.find((c) => c.connector_type === "GOOGLE_GMAIL_CONNECTOR") ?? null;

	return { authUrl: auth_url, finalUrl: location, connector };
}

/**
 * Drives the native Google Calendar OAuth flow programmatically.
 *
 * The E2E backend patches Google OAuth so the returned auth_url points
 * straight back to the backend callback with a deterministic code/state.
 */
export async function runNativeGoogleCalendarOAuth(
	request: APIRequestContext,
	token: string,
	searchSpaceId: number
): Promise<{
	authUrl: string;
	finalUrl: string;
	connector: ConnectorRow | null;
}> {
	const initiateResp = await request.get(
		`${BACKEND_URL}/api/v1/auth/google/calendar/connector/add?space_id=${searchSpaceId}`,
		{ headers: authHeaders(token) }
	);
	if (!initiateResp.ok()) {
		throw new Error(
			`native Google Calendar initiate failed (${initiateResp.status()}): ${await initiateResp.text()}`
		);
	}
	const { auth_url } = (await initiateResp.json()) as { auth_url: string };
	if (!auth_url) {
		throw new Error("native Google Calendar initiate response missing auth_url");
	}

	const callbackResp = await request.get(auth_url, {
		headers: authHeaders(token),
		maxRedirects: 0,
		failOnStatusCode: false,
	});
	const location = callbackResp.headers().location ?? auth_url;

	const connectors = await listConnectors(request, token, searchSpaceId);
	const connector =
		connectors.find((c) => c.connector_type === "GOOGLE_CALENDAR_CONNECTOR") ?? null;

	return { authUrl: auth_url, finalUrl: location, connector };
}

/**
 * Drives the Notion OAuth flow programmatically.
 *
 * The E2E backend keeps SurfSense's OAuth add/callback routes real and
 * patches only Notion's external token endpoint. Notion's authorization
 * URL stays off-origin, so this helper extracts the signed state and calls
 * the backend callback directly with the deterministic fake code.
 */
export async function runNotionOAuth(
	request: APIRequestContext,
	token: string,
	searchSpaceId: number
): Promise<{
	authUrl: string;
	finalUrl: string;
	connector: ConnectorRow | null;
}> {
	const initiateResp = await request.get(
		`${BACKEND_URL}/api/v1/auth/notion/connector/add?space_id=${searchSpaceId}`,
		{ headers: authHeaders(token) }
	);
	if (!initiateResp.ok()) {
		throw new Error(
			`Notion initiate failed (${initiateResp.status()}): ${await initiateResp.text()}`
		);
	}
	const { auth_url } = (await initiateResp.json()) as { auth_url: string };
	if (!auth_url) {
		throw new Error("Notion initiate response missing auth_url");
	}

	const state = new URL(auth_url).searchParams.get("state");
	if (!state) {
		throw new Error(`Notion auth_url missing state: ${auth_url}`);
	}

	const callbackResp = await request.get(
		`${BACKEND_URL}/api/v1/auth/notion/connector/callback?code=fake-notion-oauth-code&state=${encodeURIComponent(state)}`,
		{
			headers: authHeaders(token),
			maxRedirects: 0,
			failOnStatusCode: false,
		}
	);
	const location = callbackResp.headers().location ?? auth_url;

	const connectors = await listConnectors(request, token, searchSpaceId);
	const connector = connectors.find((c) => c.connector_type === "NOTION_CONNECTOR") ?? null;

	return { authUrl: auth_url, finalUrl: location, connector };
}

/**
 * Drives the Confluence OAuth flow programmatically.
 *
 * The E2E backend keeps SurfSense's OAuth add/callback routes real and
 * patches only Atlassian's external token/resource endpoints.
 */
export async function runConfluenceOAuth(
	request: APIRequestContext,
	token: string,
	searchSpaceId: number
): Promise<{
	authUrl: string;
	finalUrl: string;
	connector: ConnectorRow | null;
}> {
	const initiateResp = await request.get(
		`${BACKEND_URL}/api/v1/auth/confluence/connector/add?space_id=${searchSpaceId}`,
		{ headers: authHeaders(token) }
	);
	if (!initiateResp.ok()) {
		throw new Error(
			`Confluence initiate failed (${initiateResp.status()}): ${await initiateResp.text()}`
		);
	}
	const { auth_url } = (await initiateResp.json()) as { auth_url: string };
	if (!auth_url) {
		throw new Error("Confluence initiate response missing auth_url");
	}

	const state = new URL(auth_url).searchParams.get("state");
	if (!state) {
		throw new Error(`Confluence auth_url missing state: ${auth_url}`);
	}

	const callbackResp = await request.get(
		`${BACKEND_URL}/api/v1/auth/confluence/connector/callback?code=fake-confluence-oauth-code&state=${encodeURIComponent(state)}`,
		{
			headers: authHeaders(token),
			maxRedirects: 0,
			failOnStatusCode: false,
		}
	);
	const location = callbackResp.headers().location ?? auth_url;

	const connectors = await listConnectors(request, token, searchSpaceId);
	const connector = connectors.find((c) => c.connector_type === "CONFLUENCE_CONNECTOR") ?? null;

	return { authUrl: auth_url, finalUrl: location, connector };
}

/**
 * Drives the Linear MCP OAuth flow programmatically.
 *
 * The E2E backend keeps SurfSense's generic MCP OAuth routes real and
 * patches Linear's external discovery/DCR/token/MCP tool boundaries.
 */
export async function runLinearOAuth(
	request: APIRequestContext,
	token: string,
	searchSpaceId: number
): Promise<{
	authUrl: string;
	finalUrl: string;
	connector: ConnectorRow | null;
}> {
	const initiateResp = await request.get(
		`${BACKEND_URL}/api/v1/auth/mcp/linear/connector/add?space_id=${searchSpaceId}`,
		{ headers: authHeaders(token) }
	);
	if (!initiateResp.ok()) {
		throw new Error(
			`Linear MCP initiate failed (${initiateResp.status()}): ${await initiateResp.text()}`
		);
	}
	const { auth_url } = (await initiateResp.json()) as { auth_url: string };
	if (!auth_url) {
		throw new Error("Linear MCP initiate response missing auth_url");
	}

	const state = new URL(auth_url).searchParams.get("state");
	if (!state) {
		throw new Error(`Linear MCP auth_url missing state: ${auth_url}`);
	}

	const callbackResp = await request.get(
		`${BACKEND_URL}/api/v1/auth/mcp/linear/connector/callback?code=fake-linear-oauth-code&state=${encodeURIComponent(state)}`,
		{
			headers: authHeaders(token),
			maxRedirects: 0,
			failOnStatusCode: false,
		}
	);
	const location = callbackResp.headers().location ?? auth_url;

	const connectors = await listConnectors(request, token, searchSpaceId);
	const connector = connectors.find((c) => c.connector_type === "LINEAR_CONNECTOR") ?? null;

	return { authUrl: auth_url, finalUrl: location, connector };
}

/**
 * Drives the Jira MCP OAuth flow programmatically.
 *
 * The E2E backend keeps SurfSense's generic MCP OAuth routes real and
 * patches Jira's external discovery/DCR/token/MCP tool boundaries.
 */
export async function runJiraOAuth(
	request: APIRequestContext,
	token: string,
	searchSpaceId: number
): Promise<{
	authUrl: string;
	finalUrl: string;
	connector: ConnectorRow | null;
}> {
	const initiateResp = await request.get(
		`${BACKEND_URL}/api/v1/auth/mcp/jira/connector/add?space_id=${searchSpaceId}`,
		{ headers: authHeaders(token) }
	);
	if (!initiateResp.ok()) {
		throw new Error(
			`Jira MCP initiate failed (${initiateResp.status()}): ${await initiateResp.text()}`
		);
	}
	const { auth_url } = (await initiateResp.json()) as { auth_url: string };
	if (!auth_url) {
		throw new Error("Jira MCP initiate response missing auth_url");
	}

	const state = new URL(auth_url).searchParams.get("state");
	if (!state) {
		throw new Error(`Jira MCP auth_url missing state: ${auth_url}`);
	}

	const callbackResp = await request.get(
		`${BACKEND_URL}/api/v1/auth/mcp/jira/connector/callback?code=fake-jira-oauth-code&state=${encodeURIComponent(state)}`,
		{
			headers: authHeaders(token),
			maxRedirects: 0,
			failOnStatusCode: false,
		}
	);
	const location = callbackResp.headers().location ?? auth_url;

	const connectors = await listConnectors(request, token, searchSpaceId);
	const connector = connectors.find((c) => c.connector_type === "JIRA_CONNECTOR") ?? null;

	return { authUrl: auth_url, finalUrl: location, connector };
}
