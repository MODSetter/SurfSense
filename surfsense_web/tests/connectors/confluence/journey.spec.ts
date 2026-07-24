import { expect, confluenceWithChatTest as test } from "../../fixtures";
import { streamChatToCompletion } from "../../helpers/api/chat";
import { listConnectors, triggerIndexExpectDisabled } from "../../helpers/api/connectors";
import { listDocuments } from "../../helpers/api/documents";
import { CANARY_TOKENS, FAKE_CONFLUENCE_PAGES } from "../../helpers/canary";
import { openConnectorPopup } from "../../helpers/ui/connector-popup";

/**
 * Proves Confluence MCP OAuth -> live MCP tool discovery/call -> chat.
 *
 * Confluence migrated to the hosted Atlassian Rovo MCP server (shared with
 * Jira), so it is live-tool only: the public indexing route returns
 * indexing_started=false and chat should call Confluence MCP tools
 * (`searchConfluenceUsingCql`) instead of retrieving from the KB.
 */
test.describe("Confluence connector journey", () => {
	test("user connects Confluence and chats through live MCP tools with indexing disabled", async ({
		page,
		request,
		apiToken,
		workspace,
		confluenceConnector,
		chatThread,
	}) => {
		test.setTimeout(90_000); // worker cold-start + live tool chat

		expect(confluenceConnector.connector_type).toBe("CONFLUENCE_CONNECTOR");
		expect(confluenceConnector.is_indexable).toBe(false);
		expect(confluenceConnector.config._token_encrypted).toBe(true);
		expect(confluenceConnector.config.mcp_service).toBe("confluence");
		expect(confluenceConnector.config.server_config).toMatchObject({
			transport: "streamable-http",
			url: "https://mcp.atlassian.com/v1/mcp",
		});
		// Shared Atlassian server issues the token via the same cf.mcp endpoint
		// as Jira; assert the endpoint + a live token rather than the (Jira-named)
		// shared client id.
		expect(confluenceConnector.config.mcp_oauth).toMatchObject({
			token_endpoint: "https://cf.mcp.atlassian.com/v1/token",
		});
		expect(
			(confluenceConnector.config.mcp_oauth as Record<string, unknown>).access_token
		).toBeTruthy();
		expect(confluenceConnector.config.access_token).toBeUndefined();
		expect(confluenceConnector.config.refresh_token).toBeUndefined();

		await page.goto(`/dashboard/${workspace.id}/new-chat`, {
			waitUntil: "domcontentloaded",
		});
		await openConnectorPopup(page);
		const connectorDialog = page.getByRole("dialog", { name: "MCP Connectors" });
		await expect(connectorDialog).toBeVisible();
		await connectorDialog.getByPlaceholder("Search").fill("Confluence");
		await expect(connectorDialog.getByText("Confluence", { exact: true })).toBeVisible();

		const beforeDocs = await listDocuments(request, apiToken, workspace.id);
		expect(beforeDocs).toHaveLength(0);

		const disabledIndex = await triggerIndexExpectDisabled(
			request,
			apiToken,
			confluenceConnector.id,
			workspace.id
		);
		expect(disabledIndex.message ?? "").toContain("real-time agent tools");
		expect(disabledIndex.message ?? "").toContain("background indexing is disabled");

		const chat = await streamChatToCompletion(request, apiToken, {
			workspaceId: workspace.id,
			threadId: chatThread.id,
			query: `What is in my Confluence page titled "${FAKE_CONFLUENCE_PAGES.canary.title}"?`,
		});
		expect(
			chat.assistantText,
			`chat agent should surface Confluence canary token from live MCP tools; got: ${chat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.confluenceCanary);

		const eventText = JSON.stringify(chat.events);
		expect(eventText).toContain("searchConfluenceUsingCql");

		const refreshedConnectors = await listConnectors(request, apiToken, workspace.id);
		const refreshed = refreshedConnectors.find((c) => c.id === confluenceConnector.id);
		expect(refreshed?.connector_type).toBe("CONFLUENCE_CONNECTOR");
		expect(refreshed?.is_indexable).toBe(false);
		expect(refreshed?.last_indexed_at).toBeNull();

		const afterDocs = await listDocuments(request, apiToken, workspace.id);
		expect(afterDocs).toHaveLength(0);
	});
});
