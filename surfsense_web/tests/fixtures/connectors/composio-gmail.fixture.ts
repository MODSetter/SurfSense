import {
	type ConnectorRow,
	deleteConnector,
	runComposioOAuth,
} from "../../helpers/api/connectors";
import { searchSpaceFixtures } from "../search-space.fixture";

export type ComposioGmailFixtures = {
	/**
	 * A pre-connected Composio Gmail connector inside the fixture's
	 * `searchSpace`. OAuth happens against the strict fake (no real
	 * network). Cleaned up automatically after the test.
	 */
	composioGmailConnector: ConnectorRow;
};

export const composioGmailFixtures = searchSpaceFixtures.extend<ComposioGmailFixtures>({
	composioGmailConnector: async ({ request, apiToken, searchSpace }, use) => {
		const { connector } = await runComposioOAuth(
			request,
			apiToken,
			searchSpace.id,
			"gmail"
		);
		if (!connector) {
			throw new Error(
				"composioGmailConnector fixture: OAuth completed but no connector was created. " +
					"Check the backend log — the strict Composio fake likely rejected an unmodelled call."
			);
		}
		try {
			await use(connector);
		} finally {
			await deleteConnector(request, apiToken, connector.id);
		}
	},
});
