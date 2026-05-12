import {
	type ConnectorRow,
	deleteConnector,
	runConfluenceOAuth,
} from "../../helpers/api/connectors";
import { searchSpaceFixtures } from "../search-space.fixture";

export type ConfluenceFixtures = {
	/**
	 * A pre-connected Confluence connector inside the fixture's `searchSpace`.
	 * OAuth uses E2E Atlassian fakes and is cleaned up automatically after
	 * the test.
	 */
	confluenceConnector: ConnectorRow;
};

export const confluenceFixtures = searchSpaceFixtures.extend<ConfluenceFixtures>({
	confluenceConnector: async ({ request, apiToken, searchSpace }, use) => {
		const { connector } = await runConfluenceOAuth(request, apiToken, searchSpace.id);
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
