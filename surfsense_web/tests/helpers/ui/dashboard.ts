import type { Page } from "@playwright/test";
import { expect } from "@playwright/test";

/**
 * Navigation helpers for dashboard routes. Centralized so that future
 * route changes only require an update in one place.
 */

export function newChatUrl(workspaceId: number): string {
	return `/dashboard/${workspaceId}/new-chat`;
}

export function connectorsCallbackUrl(workspaceId: number): string {
	return `/dashboard/${workspaceId}/connectors/callback`;
}

export async function gotoNewChat(page: Page, workspaceId: number): Promise<void> {
	const target = newChatUrl(workspaceId);
	await page.goto(target, { waitUntil: "domcontentloaded" });
	await expect(page).toHaveURL((url) => url.pathname === target);
}
