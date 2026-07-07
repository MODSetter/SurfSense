import { expect, clickupWithChatTest as test } from "../../fixtures";
import { streamChatToCompletion } from "../../helpers/api/chat";
import { listConnectors, triggerIndexExpectDisabled } from "../../helpers/api/connectors";
import { listDocuments } from "../../helpers/api/documents";
import { CANARY_TOKENS, FAKE_CLICKUP_TASKS } from "../../helpers/canary";
import { openConnectorPopup } from "../../helpers/ui/connector-popup";

/**
 * Proves ClickUp MCP OAuth -> live MCP tool discovery/call -> chat.
 *
 * ClickUp is live-tool only: the public indexing route returns
 * indexing_started=false and chat should call ClickUp MCP tools.
 */
test.describe("ClickUp connector journey", () => {
	test("user connects ClickUp and chats through live MCP tools with indexing disabled", async ({
		page,
		request,
		apiToken,
		workspace,
		clickupConnector,
		chatThread,
	}) => {
		test.setTimeout(90_000); // worker cold-start + live tool chat

		expect(clickupConnector.connector_type).toBe("CLICKUP_CONNECTOR");
		expect(clickupConnector.is_indexable).toBe(false);
		expect(clickupConnector.config._token_encrypted).toBe(true);
		expect(clickupConnector.config.mcp_service).toBe("clickup");
		expect(clickupConnector.config.server_config).toMatchObject({
			transport: "streamable-http",
			url: "https://mcp.clickup.com/mcp",
		});
		expect(clickupConnector.config.mcp_oauth).toMatchObject({
			client_id: "fake-clickup-mcp-client-id",
			token_endpoint: "https://mcp.clickup.com/token",
		});
		expect(
			(clickupConnector.config.mcp_oauth as Record<string, unknown>).access_token
		).toBeTruthy();
		expect(clickupConnector.config.access_token).toBeUndefined();
		expect(clickupConnector.config.refresh_token).toBeUndefined();

		await page.goto(`/dashboard/${workspace.id}/new-chat`, {
			waitUntil: "domcontentloaded",
		});
		await openConnectorPopup(page);
		const connectorDialog = page.getByRole("dialog", { name: "Manage External MCP Connectors" });
		await expect(connectorDialog).toBeVisible();
		await expect(connectorDialog.getByText("ClickUp")).toBeVisible();

		const beforeDocs = await listDocuments(request, apiToken, workspace.id);
		expect(beforeDocs).toHaveLength(0);

		const disabledIndex = await triggerIndexExpectDisabled(
			request,
			apiToken,
			clickupConnector.id,
			workspace.id
		);
		expect(disabledIndex.message ?? "").toContain("real-time agent tools");
		expect(disabledIndex.message ?? "").toContain("background indexing is disabled");

		const chat = await streamChatToCompletion(request, apiToken, {
			workspaceId: workspace.id,
			threadId: chatThread.id,
			query: `What is in my ClickUp task titled "${FAKE_CLICKUP_TASKS.canary.name}"?`,
		});
		expect(
			chat.assistantText,
			`chat agent should surface ClickUp canary token from live MCP tools; got: ${chat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.clickupCanary);

		const eventText = JSON.stringify(chat.events);
		expect(eventText).toContain("clickup_search");

		const refreshedConnectors = await listConnectors(request, apiToken, workspace.id);
		const refreshed = refreshedConnectors.find((c) => c.id === clickupConnector.id);
		expect(refreshed?.connector_type).toBe("CLICKUP_CONNECTOR");
		expect(refreshed?.is_indexable).toBe(false);
		expect(refreshed?.last_indexed_at).toBeNull();

		const afterDocs = await listDocuments(request, apiToken, workspace.id);
		expect(afterDocs).toHaveLength(0);
	});
});
