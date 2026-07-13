import { expect, linearWithChatTest as test } from "../../fixtures";
import { streamChatToCompletion } from "../../helpers/api/chat";
import { listConnectors, triggerIndexExpectDisabled } from "../../helpers/api/connectors";
import { listDocuments } from "../../helpers/api/documents";
import { CANARY_TOKENS, FAKE_LINEAR_ISSUES } from "../../helpers/canary";
import { openConnectorPopup } from "../../helpers/ui/connector-popup";

/**
 * Proves Linear MCP OAuth -> live MCP tool discovery/call -> chat.
 *
 * Linear is live-tool only: the public indexing route returns
 * indexing_started=false and chat should call Linear MCP tools.
 */
test.describe("Linear connector journey", () => {
	test("user connects Linear and chats through live MCP tools with indexing disabled", async ({
		page,
		request,
		apiToken,
		workspace,
		linearConnector,
		chatThread,
	}) => {
		test.setTimeout(90_000); // worker cold-start + live tool chat

		expect(linearConnector.connector_type).toBe("LINEAR_CONNECTOR");
		expect(linearConnector.is_indexable).toBe(false);
		expect(linearConnector.config._token_encrypted).toBe(true);
		expect(linearConnector.config.mcp_service).toBe("linear");
		expect(linearConnector.config.server_config).toMatchObject({
			transport: "streamable-http",
			url: "https://mcp.linear.app/mcp",
		});
		expect(linearConnector.config.mcp_oauth).toMatchObject({
			client_id: "fake-linear-mcp-client-id",
			token_endpoint: "https://mcp.linear.app/token",
		});
		expect((linearConnector.config.mcp_oauth as Record<string, unknown>).access_token).toBeTruthy();
		expect(linearConnector.config.access_token).toBeUndefined();
		expect(linearConnector.config.refresh_token).toBeUndefined();

		await page.goto(`/dashboard/${workspace.id}/new-chat`, {
			waitUntil: "domcontentloaded",
		});
		await openConnectorPopup(page);
		const connectorDialog = page.getByRole("dialog", { name: "MCP Connectors" });
		await expect(connectorDialog).toBeVisible();

		const beforeDocs = await listDocuments(request, apiToken, workspace.id);
		expect(beforeDocs).toHaveLength(0);

		const disabledIndex = await triggerIndexExpectDisabled(
			request,
			apiToken,
			linearConnector.id,
			workspace.id
		);
		expect(disabledIndex.message ?? "").toContain("real-time agent tools");
		expect(disabledIndex.message ?? "").toContain("background indexing is disabled");

		const chat = await streamChatToCompletion(request, apiToken, {
			workspaceId: workspace.id,
			threadId: chatThread.id,
			query: `What is in my Linear issue titled "${FAKE_LINEAR_ISSUES.canary.title}"?`,
		});
		expect(
			chat.assistantText,
			`chat agent should surface Linear canary token from live MCP tools; got: ${chat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.linearCanary);

		const eventText = JSON.stringify(chat.events);
		expect(eventText).toContain("list_issues");

		const refreshedConnectors = await listConnectors(request, apiToken, workspace.id);
		const refreshed = refreshedConnectors.find((c) => c.id === linearConnector.id);
		expect(refreshed?.connector_type).toBe("LINEAR_CONNECTOR");
		expect(refreshed?.is_indexable).toBe(false);
		expect(refreshed?.last_indexed_at).toBeNull();

		const afterDocs = await listDocuments(request, apiToken, workspace.id);
		expect(afterDocs).toHaveLength(0);
	});
});
