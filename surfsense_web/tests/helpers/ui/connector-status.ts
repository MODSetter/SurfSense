import type { Page } from "@playwright/test";

/**
 * Selectors for connector status indicators (last_indexed_at badge,
 * indexing spinner, auth-expired banner). Reserved for Phase 2 UI-level
 * assertions; Phase 1 specs assert these via the API.
 */
export async function reservedForPhaseTwo(_page: Page): Promise<void> {
	// Intentionally empty.
}
