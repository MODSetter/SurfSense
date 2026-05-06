import {
	type ConnectorRow,
	deleteConnector,
	runNativeGoogleDriveOAuth,
} from "../../helpers/api/connectors";
import { searchSpaceFixtures } from "../search-space.fixture";

export type NativeDriveFixtures = {
	/**
	 * A pre-connected native Google Drive connector inside the fixture's
	 * `searchSpace`. OAuth uses E2E native Google fakes and is cleaned up
	 * automatically after the test.
	 */
	nativeDriveConnector: ConnectorRow;
};

export const nativeDriveFixtures = searchSpaceFixtures.extend<NativeDriveFixtures>({
	nativeDriveConnector: async ({ request, apiToken, searchSpace }, use) => {
		const { connector } = await runNativeGoogleDriveOAuth(request, apiToken, searchSpace.id);
		if (!connector) {
			throw new Error(
				"nativeDriveConnector fixture: OAuth completed but no GOOGLE_DRIVE_CONNECTOR was created. " +
					"Check the backend log — the native Google Drive fake likely rejected an unmodelled call."
			);
		}
		try {
			await use(connector);
		} finally {
			await deleteConnector(request, apiToken, connector.id);
		}
	},
});
