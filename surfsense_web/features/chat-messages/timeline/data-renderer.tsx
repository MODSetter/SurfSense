"use client";

import { makeAssistantDataUI } from "@assistant-ui/react";

/**
 * assistant-ui registrar for the canonical ``data-activities`` part.
 *
 * Re-scopes the global ``PendingInterruptProvider`` per message: approval
 * cards only mount under the assistant message that owns the interrupt
 * (otherwise every message in scrollback would render its own cards).
 */
function TimelineDataRenderer() {
	// TurnActivity is the sole per-message process renderer.
	return null;
}

export const TimelineDataUI = makeAssistantDataUI({
	name: "activities",
	render: TimelineDataRenderer,
});
