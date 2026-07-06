import {
	type ConnectorRow,
	deleteConnector,
	runNativeDropboxOAuth,
} from "../../helpers/api/connectors";
import { searchSpaceFixtures } from "../workspace.fixture";

export type NativeDropboxFixtures = {
	/**
	 * A pre-connected native Dropbox connector inside the fixture's
	 * `searchSpace`. OAuth uses E2E Dropbox fakes and is cleaned up
	 * automatically after the test.
	 */
	nativeDropboxConnector: ConnectorRow;
};

export const nativeDropboxFixtures = searchSpaceFixtures.extend<NativeDropboxFixtures>({
	nativeDropboxConnector: async ({ request, apiToken, searchSpace }, use) => {
		const { connector } = await runNativeDropboxOAuth(request, apiToken, searchSpace.id);
		if (!connector) {
			throw new Error(
				"nativeDropboxConnector fixture: OAuth completed but no DROPBOX_CONNECTOR was created. " +
					"Check the backend log — the Dropbox fake likely rejected an unmodelled call."
			);
		}
		try {
			await use(connector);
		} finally {
			await deleteConnector(request, apiToken, connector.id);
		}
	},
});
