import { expect, jiraWithChatTest as test } from "../../fixtures";
import { streamChatToCompletion } from "../../helpers/api/chat";
import { listConnectors, triggerIndexExpectDisabled } from "../../helpers/api/connectors";
import { listDocuments } from "../../helpers/api/documents";
import { CANARY_TOKENS, FAKE_JIRA_ISSUES } from "../../helpers/canary";
import { openConnectorPopup } from "../../helpers/ui/connector-popup";

/**
 * Proves Jira MCP OAuth -> live MCP tool discovery/call -> chat.
 *
 * Jira is live-tool only: the public indexing route returns
 * indexing_started=false and chat should call Jira MCP tools.
 */
test.describe("Jira connector journey", () => {
	test("user connects Jira and chats through live MCP tools with indexing disabled", async ({
		page,
		request,
		apiToken,
		workspace,
		jiraConnector,
		chatThread,
	}) => {
		test.setTimeout(90_000); // worker cold-start + live tool chat

		expect(jiraConnector.connector_type).toBe("JIRA_CONNECTOR");
		expect(jiraConnector.is_indexable).toBe(false);
		expect(jiraConnector.config._token_encrypted).toBe(true);
		expect(jiraConnector.config.mcp_service).toBe("jira");
		expect(jiraConnector.config.server_config).toMatchObject({
			transport: "streamable-http",
			url: "https://mcp.atlassian.com/v1/mcp",
		});
		expect(jiraConnector.config.mcp_oauth).toMatchObject({
			client_id: "fake-jira-mcp-client-id",
			token_endpoint: "https://cf.mcp.atlassian.com/v1/token",
		});
		expect((jiraConnector.config.mcp_oauth as Record<string, unknown>).access_token).toBeTruthy();
		expect(jiraConnector.config.access_token).toBeUndefined();
		expect(jiraConnector.config.refresh_token).toBeUndefined();

		await page.goto(`/dashboard/${workspace.id}/new-chat`, {
			waitUntil: "domcontentloaded",
		});
		await openConnectorPopup(page);
		const connectorDialog = page.getByRole("dialog", { name: "Manage External MCP Connectors" });
		await expect(connectorDialog).toBeVisible();
		await connectorDialog.getByPlaceholder("Search").fill("Jira");
		await expect(connectorDialog.getByText("Jira", { exact: true })).toBeVisible();

		const beforeDocs = await listDocuments(request, apiToken, workspace.id);
		expect(beforeDocs).toHaveLength(0);

		const disabledIndex = await triggerIndexExpectDisabled(
			request,
			apiToken,
			jiraConnector.id,
			workspace.id
		);
		expect(disabledIndex.message ?? "").toContain("real-time agent tools");
		expect(disabledIndex.message ?? "").toContain("background indexing is disabled");

		const chat = await streamChatToCompletion(request, apiToken, {
			workspaceId: workspace.id,
			threadId: chatThread.id,
			query: `What is in my Jira issue titled "${FAKE_JIRA_ISSUES.canary.summary}"?`,
		});
		expect(
			chat.assistantText,
			`chat agent should surface Jira canary token from live MCP tools; got: ${chat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.jiraCanary);

		const eventText = JSON.stringify(chat.events);
		expect(eventText).toContain("searchJiraIssuesUsingJql");

		const refreshedConnectors = await listConnectors(request, apiToken, workspace.id);
		const refreshed = refreshedConnectors.find((c) => c.id === jiraConnector.id);
		expect(refreshed?.connector_type).toBe("JIRA_CONNECTOR");
		expect(refreshed?.is_indexable).toBe(false);
		expect(refreshed?.last_indexed_at).toBeNull();

		const afterDocs = await listDocuments(request, apiToken, workspace.id);
		expect(afterDocs).toHaveLength(0);
	});
});
