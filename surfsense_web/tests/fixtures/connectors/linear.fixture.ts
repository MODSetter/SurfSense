import { type ConnectorRow, deleteConnector, runLinearOAuth } from "../../helpers/api/connectors";
import { workspaceFixtures } from "../workspace.fixture";

export type LinearFixtures = {
	/**
	 * A pre-connected Linear connector inside the fixture's `workspace`.
	 * OAuth and MCP tool calls use E2E Linear fakes and are cleaned up
	 * automatically after the test.
	 */
	linearConnector: ConnectorRow;
};

export const linearFixtures = workspaceFixtures.extend<LinearFixtures>({
	linearConnector: async ({ request, apiToken, workspace }, use) => {
		const { connector } = await runLinearOAuth(request, apiToken, workspace.id);
		if (!connector) {
			throw new Error(
				"linearConnector fixture: OAuth completed but no LINEAR_CONNECTOR was created. " +
					"Check the backend log — the Linear MCP fake likely rejected an unmodelled call."
			);
		}
		try {
			await use(connector);
		} finally {
			await deleteConnector(request, apiToken, connector.id);
		}
	},
});
