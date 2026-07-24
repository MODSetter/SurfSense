import type { Page } from "@playwright/test";
import { expect } from "@playwright/test";

/**
 * Page-object-style helpers for the connector dialog rendered by
 * components/assistant-ui/connector-popup.tsx.
 *
 * Kept minimal in Phase 1: most spec interactions go through API
 * fixtures for determinism. UI-driven coverage of every connector card
 * is a Phase 2 task and will use this helper as the entry point.
 */

export async function openConnectorPopup(page: Page): Promise<void> {
	// Label depends on whether the user already has connectors.
	const trigger = page
		.getByRole("button", { name: "Manage connectors" })
		.or(page.getByRole("button", { name: "Connect your connectors" }))
		.first();

	// Long timeout absorbs Next.js dev cold-compile of the new-chat route.
	await expect(trigger).toBeVisible({ timeout: 60_000 });
	await trigger.click();

	await expect(page.getByRole("dialog", { name: "MCP Connectors" })).toBeVisible();
}

/**
 * Opens the Documents sidebar "Import" menu. Import connectors
 * (Google Drive / OneDrive / Dropbox) are surfaced here instead of in the
 * external-MCP connector catalog.
 */
export async function openDocumentsImportMenu(page: Page): Promise<void> {
	const trigger = page.getByRole("button", { name: "Import documents" }).first();
	// Long timeout absorbs Next.js dev cold-compile of the dashboard route.
	await expect(trigger).toBeVisible({ timeout: 60_000 });
	await trigger.click();
}

/**
 * Opens the Import menu and asserts a cloud-drive import connector is offered.
 * `label` is the visible menu label ("Google Drive", "OneDrive", "Dropbox").
 */
export async function expectImportConnectorAvailable(page: Page, label: string): Promise<void> {
	await openDocumentsImportMenu(page);
	await expect(page.getByRole("menuitem", { name: label })).toBeVisible();
	await page.keyboard.press("Escape");
}
