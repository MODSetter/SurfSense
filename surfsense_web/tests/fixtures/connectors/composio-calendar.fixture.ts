import { type ConnectorRow, deleteConnector, runComposioOAuth } from "../../helpers/api/connectors";
import { workspaceFixtures } from "../workspace.fixture";

export type ComposioCalendarFixtures = {
	/**
	 * A pre-connected Composio Google Calendar connector inside the
	 * fixture's `workspace`. OAuth uses the strict fake and is cleaned
	 * up automatically after the test.
	 */
	composioCalendarConnector: ConnectorRow;
};

export const composioCalendarFixtures = workspaceFixtures.extend<ComposioCalendarFixtures>({
	composioCalendarConnector: async ({ request, apiToken, workspace }, use) => {
		const { connector } = await runComposioOAuth(request, apiToken, workspace.id, "googlecalendar");
		if (!connector) {
			throw new Error(
				"composioCalendarConnector fixture: OAuth completed but no connector was created. " +
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
