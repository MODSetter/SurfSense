import { type ConnectorRow, deleteConnector, runSlackOAuth } from "../../helpers/api/connectors";
import { workspaceFixtures } from "../workspace.fixture";

export type SlackFixtures = {
	/**
	 * A pre-connected Slack connector inside the fixture's `workspace`.
	 * OAuth and MCP tool calls use E2E Slack fakes and are cleaned up
	 * automatically after the test.
	 */
	slackConnector: ConnectorRow;
};

export const slackFixtures = workspaceFixtures.extend<SlackFixtures>({
	slackConnector: async ({ request, apiToken, workspace }, use) => {
		const { connector } = await runSlackOAuth(request, apiToken, workspace.id);
		if (!connector) {
			throw new Error(
				"slackConnector fixture: OAuth completed but no SLACK_CONNECTOR was created. " +
					"Check the backend log — the Slack MCP fake likely rejected an unmodelled call."
			);
		}
		try {
			await use(connector);
		} finally {
			await deleteConnector(request, apiToken, connector.id);
		}
	},
});
