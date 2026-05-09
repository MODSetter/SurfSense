import { useCallback } from "react";
import { useHitlBundle, useToolCallIdContext } from "./bundle/bundle-context";
import type { HitlDecision } from "./types";

/**
 * Dispatches a HITL decision from inside an approval card.
 *
 * Behavior:
 *  - **Bundle active** (N≥2 parallel interrupts) AND this card's
 *    ``toolCallId`` is in the bundle: stage the (single) decision
 *    against this ``toolCallId`` so the bundle can submit one ordered
 *    N-payload when every card has decided. Multi-decision dispatches
 *    in this path are a programming error: only ``decisions[0]`` is
 *    staged; a dev warning fires for the rest.
 *  - **Otherwise (N=1 or no bundle):** dispatch the ``hitl-decision``
 *    window event directly with the full ``decisions`` array. The host
 *    page's listener calls ``runtime.resume`` with the same array.
 *
 * Cards always call ``dispatch([decision])`` and don't need to know
 * which path they're on.
 */
export function useHitlDecision() {
	const bundle = useHitlBundle();
	const toolCallId = useToolCallIdContext();

	const dispatch = useCallback(
		(decisions: HitlDecision[]) => {
			if (bundle && toolCallId && bundle.isInBundle(toolCallId) && decisions.length > 0) {
				if (decisions.length > 1 && process.env.NODE_ENV !== "production") {
					console.warn(
						"[hitl] dispatch received %d decisions inside an active bundle; only [0] will be staged for %s",
						decisions.length,
						toolCallId
					);
				}
				bundle.stage(toolCallId, decisions[0]);
				return;
			}
			window.dispatchEvent(new CustomEvent("hitl-decision", { detail: { decisions } }));
		},
		[bundle, toolCallId]
	);

	return { dispatch };
}
