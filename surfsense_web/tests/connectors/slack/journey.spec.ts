import { expect, slackWithChatTest as test } from "../../fixtures";
import { streamChatToCompletion } from "../../helpers/api/chat";
import { listConnectors, triggerIndexExpectDisabled } from "../../helpers/api/connectors";
import { listDocuments } from "../../helpers/api/documents";
import { CANARY_TOKENS, FAKE_SLACK_CHANNELS } from "../../helpers/canary";
import { openConnectorPopup } from "../../helpers/ui/connector-popup";

/**
 * Proves Slack MCP OAuth -> live MCP tool discovery/call -> chat.
 *
 * Slack is live-tool only: the public indexing route returns
 * indexing_started=false and chat should call Slack MCP tools.
 */
test.describe("Slack connector journey", () => {
	test("user connects Slack and chats through live MCP tools with indexing disabled", async ({
		page,
		request,
		apiToken,
		workspace,
		slackConnector,
		chatThread,
	}) => {
		test.setTimeout(90_000); // worker cold-start + live tool chat

		expect(slackConnector.connector_type).toBe("SLACK_CONNECTOR");
		expect(slackConnector.is_indexable).toBe(false);
		expect(slackConnector.config._token_encrypted).toBe(true);
		expect(slackConnector.config.mcp_service).toBe("slack");
		expect(slackConnector.config.server_config).toMatchObject({
			transport: "streamable-http",
			url: "https://mcp.slack.com/mcp",
		});
		expect(slackConnector.config.mcp_oauth).toMatchObject({
			client_id: "fake-slack-mcp-client-id",
			token_endpoint: "https://slack.com/api/oauth.v2.user.access",
		});
		expect((slackConnector.config.mcp_oauth as Record<string, unknown>).access_token).toBeTruthy();
		expect(slackConnector.config.access_token).toBeUndefined();
		expect(slackConnector.config.refresh_token).toBeUndefined();
		expect(slackConnector.config.team_id).toBe(FAKE_SLACK_CHANNELS.canary.teamId);
		expect(slackConnector.config.team_name).toBe(FAKE_SLACK_CHANNELS.canary.teamName);

		await page.goto(`/dashboard/${workspace.id}/new-chat`, {
			waitUntil: "domcontentloaded",
		});
		await openConnectorPopup(page);
		const connectorDialog = page.getByRole("dialog", { name: "Manage Connectors" });
		await expect(connectorDialog).toBeVisible();
		await connectorDialog.getByPlaceholder("Search").fill("Slack");
		await expect(connectorDialog.getByText("Slack", { exact: true })).toBeVisible();

		const beforeDocs = await listDocuments(request, apiToken, workspace.id);
		expect(beforeDocs).toHaveLength(0);

		const disabledIndex = await triggerIndexExpectDisabled(
			request,
			apiToken,
			slackConnector.id,
			workspace.id
		);
		expect(disabledIndex.message ?? "").toContain("real-time agent tools");
		expect(disabledIndex.message ?? "").toContain("background indexing is disabled");

		const chat = await streamChatToCompletion(request, apiToken, {
			workspaceId: workspace.id,
			threadId: chatThread.id,
			query: `What is in my Slack channel "${FAKE_SLACK_CHANNELS.canary.name}"?`,
		});
		expect(
			chat.assistantText,
			`chat agent should surface Slack canary token from live MCP tools; got: ${chat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.slackCanary);

		const eventText = JSON.stringify(chat.events);
		expect(eventText).toContain("slack_search_channels");

		const refreshedConnectors = await listConnectors(request, apiToken, workspace.id);
		const refreshed = refreshedConnectors.find((c) => c.id === slackConnector.id);
		expect(refreshed?.connector_type).toBe("SLACK_CONNECTOR");
		expect(refreshed?.is_indexable).toBe(false);
		expect(refreshed?.last_indexed_at).toBeNull();

		const afterDocs = await listDocuments(request, apiToken, workspace.id);
		expect(afterDocs).toHaveLength(0);
	});
});
