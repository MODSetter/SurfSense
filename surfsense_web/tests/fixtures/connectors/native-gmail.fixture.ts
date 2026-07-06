import {
	type ConnectorRow,
	deleteConnector,
	runNativeGoogleGmailOAuth,
} from "../../helpers/api/connectors";
import { searchSpaceFixtures } from "../workspace.fixture";

export type NativeGmailFixtures = {
	/**
	 * A pre-connected native Google Gmail connector inside the fixture's
	 * `searchSpace`. OAuth uses E2E native Google fakes and is cleaned up
	 * automatically after the test.
	 */
	nativeGmailConnector: ConnectorRow;
};

export const nativeGmailFixtures = searchSpaceFixtures.extend<NativeGmailFixtures>({
	nativeGmailConnector: async ({ request, apiToken, searchSpace }, use) => {
		const { connector } = await runNativeGoogleGmailOAuth(request, apiToken, searchSpace.id);
		if (!connector) {
			throw new Error(
				"nativeGmailConnector fixture: OAuth completed but no GOOGLE_GMAIL_CONNECTOR was created. " +
					"Check the backend log — the native Google fake likely rejected an unmodelled call."
			);
		}
		try {
			await use(connector);
		} finally {
			await deleteConnector(request, apiToken, connector.id);
		}
	},
});
