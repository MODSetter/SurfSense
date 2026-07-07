import {
	type ConnectorRow,
	deleteConnector,
	runNativeGoogleDriveOAuth,
} from "../../helpers/api/connectors";
import { workspaceFixtures } from "../workspace.fixture";

export type NativeDriveFixtures = {
	/**
	 * A pre-connected native Google Drive connector inside the fixture's
	 * `workspace`. OAuth uses E2E native Google fakes and is cleaned up
	 * automatically after the test.
	 */
	nativeDriveConnector: ConnectorRow;
};

export const nativeDriveFixtures = workspaceFixtures.extend<NativeDriveFixtures>({
	nativeDriveConnector: async ({ request, apiToken, workspace }, use) => {
		const { connector } = await runNativeGoogleDriveOAuth(request, apiToken, workspace.id);
		if (!connector) {
			throw new Error(
				"nativeDriveConnector fixture: OAuth completed but no GOOGLE_DRIVE_CONNECTOR was created. " +
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
