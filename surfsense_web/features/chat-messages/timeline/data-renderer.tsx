"use client";

import { makeAssistantDataUI } from "@assistant-ui/react";

/**
 * assistant-ui data UI for the ``thinking-steps`` data-part.
 *
 * Re-scopes the global ``PendingInterruptProvider`` per message: approval
 * cards only mount under the assistant message that owns the interrupt
 * (otherwise every message in scrollback would render its own cards).
 */
function TimelineDataRenderer() {
	// TurnActivity is the sole per-message process renderer. Keep this
	// registrar so legacy data-thinking-steps parts remain recognized.
	return null;
}

/** Registers under ``thinking-steps`` so consumers swap the import only. */
export const TimelineDataUI = makeAssistantDataUI({
	name: "thinking-steps",
	render: TimelineDataRenderer,
});
