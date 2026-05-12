import type { Page } from "@playwright/test";
import { expect } from "@playwright/test";

/**
 * Navigation helpers for dashboard routes. Centralized so that future
 * route changes only require an update in one place.
 */

export function newChatUrl(searchSpaceId: number): string {
	return `/dashboard/${searchSpaceId}/new-chat`;
}

export function connectorsCallbackUrl(searchSpaceId: number): string {
	return `/dashboard/${searchSpaceId}/connectors/callback`;
}

export async function gotoNewChat(page: Page, searchSpaceId: number): Promise<void> {
	const target = newChatUrl(searchSpaceId);
	await page.goto(target, { waitUntil: "domcontentloaded" });
	await expect(page).toHaveURL((url) => url.pathname === target);
}
