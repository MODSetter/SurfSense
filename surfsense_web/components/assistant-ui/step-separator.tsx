"use client";

import { makeAssistantDataUI } from "@assistant-ui/react";

/**
 * Renders a thin horizontal divider between model steps within a single
 * assistant turn. The data part is pushed by `addStepSeparator` in
 * `streaming-state.ts` whenever a `start-step` SSE event arrives after
 * the message already has non-step content.
 *
 * Today the backend emits one `start-step` / `finish-step` pair per turn,
 * so most messages won't contain a separator. The renderer is wired up so
 * the planned per-model-step refactor (A2 follow-up) can light up without
 * touching the persistence path.
 */
function StepSeparatorDataRenderer() {
	return (
		<div className="mx-auto my-3 w-full max-w-(--thread-max-width) px-2">
			<div className="border-t border-border/60" />
		</div>
	);
}

export const StepSeparatorDataUI = makeAssistantDataUI({
	name: "step-separator",
	render: StepSeparatorDataRenderer,
});
