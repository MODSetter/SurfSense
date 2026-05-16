import {
	type ConnectorRow,
	deleteConnector,
	runNativeOneDriveOAuth,
} from "../../helpers/api/connectors";
import { searchSpaceFixtures } from "../search-space.fixture";

export type NativeOneDriveFixtures = {
	/**
	 * A pre-connected native Microsoft OneDrive connector inside the
	 * fixture's `searchSpace`. OAuth uses E2E Microsoft Graph fakes and is
	 * cleaned up automatically after the test.
	 */
	nativeOneDriveConnector: ConnectorRow;
};

export const nativeOneDriveFixtures = searchSpaceFixtures.extend<NativeOneDriveFixtures>({
	nativeOneDriveConnector: async ({ request, apiToken, searchSpace }, use) => {
		const { connector } = await runNativeOneDriveOAuth(request, apiToken, searchSpace.id);
		if (!connector) {
			throw new Error(
				"nativeOneDriveConnector fixture: OAuth completed but no ONEDRIVE_CONNECTOR was created. " +
					"Check the backend log — the OneDrive fake likely rejected an unmodelled call."
			);
		}
		try {
			await use(connector);
		} finally {
			await deleteConnector(request, apiToken, connector.id);
		}
	},
});
