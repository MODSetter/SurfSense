import { type ConnectorRow, deleteConnector, runSlackOAuth } from "../../helpers/api/connectors";
import { searchSpaceFixtures } from "../workspace.fixture";

export type SlackFixtures = {
	/**
	 * A pre-connected Slack connector inside the fixture's `searchSpace`.
	 * OAuth and MCP tool calls use E2E Slack fakes and are cleaned up
	 * automatically after the test.
	 */
	slackConnector: ConnectorRow;
};

export const slackFixtures = searchSpaceFixtures.extend<SlackFixtures>({
	slackConnector: async ({ request, apiToken, searchSpace }, use) => {
		const { connector } = await runSlackOAuth(request, apiToken, searchSpace.id);
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
