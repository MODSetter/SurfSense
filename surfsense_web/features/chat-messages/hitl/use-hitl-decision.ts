import { useCallback } from "react";
import { useHitlApproval } from "./approval/approval-context";
import type { HitlDecision } from "./types";

/**
 * Per-tool components always call ``dispatch([decision])``. We route
 * through ``HitlApprovalContext`` when mounted inside an approval
 * card (so multi-approval can stage and pager-navigate), and fall
 * back to the ``hitl-decision`` window event for standalone callers.
 */
export function useHitlDecision() {
	const approval = useHitlApproval();

	const dispatch = useCallback(
		(decisions: HitlDecision[]) => {
			if (approval && decisions.length > 0) {
				if (decisions.length > 1 && process.env.NODE_ENV !== "production") {
					console.warn(
						"[hitl] dispatch received %d decisions inside an approval card; only [0] will be staged",
						decisions.length
					);
				}
				approval.stage(decisions[0]);
				return;
			}
			window.dispatchEvent(new CustomEvent("hitl-decision", { detail: { decisions } }));
		},
		[approval]
	);

	return { dispatch };
}
