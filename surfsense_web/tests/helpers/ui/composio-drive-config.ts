import type { Page } from "@playwright/test";

/**
 * Placeholder for the Composio Drive configuration view (folder
 * selector + indexing options) rendered by ConnectorEditView.
 *
 * Phase 1 specs drive folder/file selection through the API helper
 * (`updateConnectorConfig`) and `triggerIndex` for determinism. UI-
 * level interaction with the folder tree is a Phase 2 task; this
 * module is reserved for those selectors.
 */
export async function reservedForPhaseTwo(_page: Page): Promise<void> {
	// Intentionally empty. See README in tests/connectors/composio/drive/.
}
