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

	await expect(page.getByRole("dialog", { name: "Manage Connectors" })).toBeVisible();
}

export async function clickComposioDriveCard(page: Page): Promise<void> {
	const composioDriveCard = page.getByText("Search your Drive files via Composio");
	await composioDriveCard.scrollIntoViewIfNeeded();
	const card = composioDriveCard
		.locator("xpath=ancestor::*[self::article or self::div][1]")
		.first();
	await card.getByRole("button", { name: "Connect" }).click();
}
