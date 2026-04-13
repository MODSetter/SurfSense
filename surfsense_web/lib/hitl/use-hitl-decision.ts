/**
 * Shared hook for dispatching HITL decisions.
 *
 * All tool-ui components that handle approve/reject/edit should use this
 * instead of manually constructing `CustomEvent("hitl-decision", ...)`.
 */

import { useCallback } from "react";
import type { HitlDecision } from "./types";

export function useHitlDecision() {
	const dispatch = useCallback((decisions: HitlDecision[]) => {
		window.dispatchEvent(
			new CustomEvent("hitl-decision", { detail: { decisions } }),
		);
	}, []);

	return { dispatch };
}
