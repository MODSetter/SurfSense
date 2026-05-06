import {
	type ConnectorRow,
	deleteConnector,
	runNativeGoogleCalendarOAuth,
} from "../../helpers/api/connectors";
import { searchSpaceFixtures } from "../search-space.fixture";

export type NativeCalendarFixtures = {
	/**
	 * A pre-connected native Google Calendar connector inside the fixture's
	 * `searchSpace`. OAuth uses E2E native Google fakes and is cleaned up
	 * automatically after the test.
	 */
	nativeCalendarConnector: ConnectorRow;
};

export const nativeCalendarFixtures = searchSpaceFixtures.extend<NativeCalendarFixtures>({
	nativeCalendarConnector: async ({ request, apiToken, searchSpace }, use) => {
		const { connector } = await runNativeGoogleCalendarOAuth(
			request,
			apiToken,
			searchSpace.id
		);
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
