import { type ConnectorRow, deleteConnector, runJiraOAuth } from "../../helpers/api/connectors";
import { searchSpaceFixtures } from "../workspace.fixture";

export type JiraFixtures = {
	/**
	 * A pre-connected Jira connector inside the fixture's `searchSpace`.
	 * OAuth and MCP tool calls use E2E Jira fakes and are cleaned up
	 * automatically after the test.
	 */
	jiraConnector: ConnectorRow;
};

export const jiraFixtures = searchSpaceFixtures.extend<JiraFixtures>({
	jiraConnector: async ({ request, apiToken, searchSpace }, use) => {
		const { connector } = await runJiraOAuth(request, apiToken, searchSpace.id);
		if (!connector) {
			throw new Error(
				"jiraConnector fixture: OAuth completed but no JIRA_CONNECTOR was created. " +
					"Check the backend log — the Jira MCP fake likely rejected an unmodelled call."
			);
		}
		try {
			await use(connector);
		} finally {
			await deleteConnector(request, apiToken, connector.id);
		}
	},
});
