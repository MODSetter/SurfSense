import {
	type ConnectorRow,
	deleteConnector,
	runConfluenceOAuth,
} from "../../helpers/api/connectors";
import { workspaceFixtures } from "../workspace.fixture";

export type ConfluenceFixtures = {
	/**
	 * A pre-connected Confluence connector inside the fixture's `workspace`.
	 * OAuth uses E2E Atlassian fakes and is cleaned up automatically after
	 * the test.
	 */
	confluenceConnector: ConnectorRow;
};

export const confluenceFixtures = workspaceFixtures.extend<ConfluenceFixtures>({
	confluenceConnector: async ({ request, apiToken, workspace }, use) => {
		const { connector } = await runConfluenceOAuth(request, apiToken, workspace.id);
		if (!connector) {
			throw new Error(
				"confluenceConnector fixture: OAuth completed but no CONFLUENCE_CONNECTOR was created. " +
					"Check the backend log — the Confluence OAuth fake likely rejected an unmodelled call."
			);
		}
		try {
			await use(connector);
		} finally {
			await deleteConnector(request, apiToken, connector.id);
		}
	},
});
