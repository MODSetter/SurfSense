import {
	type ConnectorRow,
	deleteConnector,
	runComposioOAuth,
} from "../../helpers/api/connectors";
import { searchSpaceFixtures } from "../search-space.fixture";

export type ComposioDriveFixtures = {
	/**
	 * A pre-connected Composio Google Drive connector inside the
	 * fixture's `searchSpace`. OAuth happens against the strict fake
	 * (no real network). Cleaned up automatically after the test.
	 */
	composioDriveConnector: ConnectorRow;
};

export const composioDriveFixtures = searchSpaceFixtures.extend<ComposioDriveFixtures>({
	composioDriveConnector: async ({ request, apiToken, searchSpace }, use) => {
		const { connector } = await runComposioOAuth(
			request,
			apiToken,
			searchSpace.id,
			"googledrive"
		);
		if (!connector) {
			throw new Error(
				"composioDriveConnector fixture: OAuth completed but no connector was created. " +
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
