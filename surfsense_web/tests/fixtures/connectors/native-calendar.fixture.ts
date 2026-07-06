import {
	type ConnectorRow,
	deleteConnector,
	runNativeGoogleCalendarOAuth,
} from "../../helpers/api/connectors";
import { workspaceFixtures } from "../workspace.fixture";

export type NativeCalendarFixtures = {
	/**
	 * A pre-connected native Google Calendar connector inside the fixture's
	 * `workspace`. OAuth uses E2E native Google fakes and is cleaned up
	 * automatically after the test.
	 */
	nativeCalendarConnector: ConnectorRow;
};

export const nativeCalendarFixtures = workspaceFixtures.extend<NativeCalendarFixtures>({
	nativeCalendarConnector: async ({ request, apiToken, workspace }, use) => {
		const { connector } = await runNativeGoogleCalendarOAuth(request, apiToken, workspace.id);
		if (!connector) {
			throw new Error(
				"nativeCalendarConnector fixture: OAuth completed but no GOOGLE_CALENDAR_CONNECTOR was created. " +
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
