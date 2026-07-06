import { type ConnectorRow, deleteConnector, runNotionOAuth } from "../../helpers/api/connectors";
import { searchSpaceFixtures } from "../workspace.fixture";

export type NotionFixtures = {
	/**
	 * A pre-connected Notion connector inside the fixture's `searchSpace`.
	 * OAuth uses E2E Notion fakes and is cleaned up automatically after the test.
	 */
	notionConnector: ConnectorRow;
};

export const notionFixtures = searchSpaceFixtures.extend<NotionFixtures>({
	notionConnector: async ({ request, apiToken, searchSpace }, use) => {
		const { connector } = await runNotionOAuth(request, apiToken, searchSpace.id);
		if (!connector) {
			throw new Error(
				"notionConnector fixture: OAuth completed but no NOTION_CONNECTOR was created. " +
					"Check the backend log — the Notion fake likely rejected an unmodelled call."
			);
		}
		try {
			await use(connector);
		} finally {
			await deleteConnector(request, apiToken, connector.id);
		}
	},
});
