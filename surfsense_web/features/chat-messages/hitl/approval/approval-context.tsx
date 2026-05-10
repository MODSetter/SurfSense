"use client";

import { createContext, useContext } from "react";
import type { HitlDecision } from "../types";

/**
 * Decisions are keyed by step index (not toolCallId) because the
 * resume protocol is positional — backend pairs ``decisions[i]`` with
 * ``action_requests[i]``. ``stage`` always targets the active step,
 * so per-tool bodies stay tcId-agnostic.
 */
export interface HitlApprovalAPI {
	total: number;
	currentStep: number;
	decisions: ReadonlyArray<HitlDecision | undefined>;
	stage: (decision: HitlDecision) => void;
	next: () => void;
	prev: () => void;
	goToStep: (i: number) => void;
	canAdvance: boolean;
	canSubmit: boolean;
}

export const HitlApprovalContext = createContext<HitlApprovalAPI | null>(null);

export function useHitlApproval(): HitlApprovalAPI | null {
	return useContext(HitlApprovalContext);
}
