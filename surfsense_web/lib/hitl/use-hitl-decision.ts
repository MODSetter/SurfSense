/**
 * Shared hook for dispatching HITL decisions.
 *
 * Tool-ui cards always call ``dispatch([decision])``. When a multi-card bundle
 * is active (``HitlBundleProvider``), the dispatch is intercepted and staged
 * against this card's ``toolCallId`` so the orchestrator can submit one
 * ordered N-decision payload. With no bundle active (N=1 path), it falls back
 * to the legacy ``window`` event the host listens for in ``page.tsx``.
 */

import { useCallback } from "react";
import { useHitlBundle, useToolCallIdContext } from "./bundle-context";
import type { HitlDecision } from "./types";

export function useHitlDecision() {
	const bundle = useHitlBundle();
	const toolCallId = useToolCallIdContext();

	const dispatch = useCallback(
		(decisions: HitlDecision[]) => {
			if (bundle && toolCallId && bundle.isInBundle(toolCallId) && decisions.length > 0) {
				bundle.stage(toolCallId, decisions[0]);
				return;
			}
			window.dispatchEvent(new CustomEvent("hitl-decision", { detail: { decisions } }));
		},
		[bundle, toolCallId]
	);

	return { dispatch };
}
