import { type ConnectorRow, deleteConnector, runClickupOAuth } from "../../helpers/api/connectors";
import { searchSpaceFixtures } from "../workspace.fixture";

export type ClickupFixtures = {
	/**
	 * A pre-connected ClickUp connector inside the fixture's `searchSpace`.
	 * OAuth and MCP tool calls use E2E ClickUp fakes and are cleaned up
	 * automatically after the test.
	 */
	clickupConnector: ConnectorRow;
};

export const clickupFixtures = searchSpaceFixtures.extend<ClickupFixtures>({
	clickupConnector: async ({ request, apiToken, searchSpace }, use) => {
		const { connector } = await runClickupOAuth(request, apiToken, searchSpace.id);
		if (!connector) {
			throw new Error(
				"clickupConnector fixture: OAuth completed but no CLICKUP_CONNECTOR was created. " +
					"Check the backend log — the ClickUp MCP fake likely rejected an unmodelled call."
			);
		}
		try {
			await use(connector);
		} finally {
			await deleteConnector(request, apiToken, connector.id);
		}
	},
});
