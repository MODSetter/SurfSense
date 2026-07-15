import { expect, notionWithChatTest as test } from "../../fixtures";
import { streamChatToCompletion } from "../../helpers/api/chat";
import { listConnectors, triggerIndexExpectDisabled } from "../../helpers/api/connectors";
import { listDocuments } from "../../helpers/api/documents";
import { CANARY_TOKENS, FAKE_NOTION_PAGES } from "../../helpers/canary";
import { openConnectorPopup } from "../../helpers/ui/connector-popup";

/**
 * Proves Notion MCP OAuth -> live MCP tool discovery/call -> chat.
 *
 * Notion migrated from indexed OAuth to the hosted Notion MCP server, so it is
 * live-tool only: the public indexing route returns indexing_started=false and
 * chat should call Notion MCP tools (`search`) instead of retrieving from the KB.
 */
test.describe("Notion connector journey", () => {
	test("user connects Notion and chats through live MCP tools with indexing disabled", async ({
		page,
		request,
		apiToken,
		workspace,
		notionConnector,
		chatThread,
	}) => {
		test.setTimeout(90_000); // worker cold-start + live tool chat

		expect(notionConnector.connector_type).toBe("NOTION_CONNECTOR");
		expect(notionConnector.is_indexable).toBe(false);
		expect(notionConnector.config._token_encrypted).toBe(true);
		expect(notionConnector.config.mcp_service).toBe("notion");
		expect(notionConnector.config.server_config).toMatchObject({
			transport: "streamable-http",
			url: "https://mcp.notion.com/mcp",
		});
		expect(notionConnector.config.mcp_oauth).toMatchObject({
			client_id: "fake-notion-mcp-client-id",
			token_endpoint: "https://mcp.notion.com/token",
		});
		expect((notionConnector.config.mcp_oauth as Record<string, unknown>).access_token).toBeTruthy();
		expect(notionConnector.config.access_token).toBeUndefined();
		expect(notionConnector.config.refresh_token).toBeUndefined();

		await page.goto(`/dashboard/${workspace.id}/new-chat`, {
			waitUntil: "domcontentloaded",
		});
		await openConnectorPopup(page);
		const connectorDialog = page.getByRole("dialog", { name: "MCP Connectors" });
		await expect(connectorDialog).toBeVisible();
		await connectorDialog.getByPlaceholder("Search").fill("Notion");
		await expect(connectorDialog.getByText("Notion", { exact: true })).toBeVisible();

		const beforeDocs = await listDocuments(request, apiToken, workspace.id);
		expect(beforeDocs).toHaveLength(0);

		const disabledIndex = await triggerIndexExpectDisabled(
			request,
			apiToken,
			notionConnector.id,
			workspace.id
		);
		expect(disabledIndex.message ?? "").toContain("real-time agent tools");
		expect(disabledIndex.message ?? "").toContain("background indexing is disabled");

		const chat = await streamChatToCompletion(request, apiToken, {
			workspaceId: workspace.id,
			threadId: chatThread.id,
			query: `What is in my Notion page titled "${FAKE_NOTION_PAGES.canary.title}"?`,
		});
		expect(
			chat.assistantText,
			`chat agent should surface Notion canary token from live MCP tools; got: ${chat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.notionCanary);

		const eventText = JSON.stringify(chat.events);
		expect(eventText).toContain(FAKE_NOTION_PAGES.canary.id);

		const refreshedConnectors = await listConnectors(request, apiToken, workspace.id);
		const refreshed = refreshedConnectors.find((c) => c.id === notionConnector.id);
		expect(refreshed?.connector_type).toBe("NOTION_CONNECTOR");
		expect(refreshed?.is_indexable).toBe(false);
		expect(refreshed?.last_indexed_at).toBeNull();

		const afterDocs = await listDocuments(request, apiToken, workspace.id);
		expect(afterDocs).toHaveLength(0);
	});
});
