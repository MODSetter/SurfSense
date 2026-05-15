"use client";

import { createContext, type ReactNode, useContext } from "react";
import type { HitlDecision } from "../types";

/** One in-flight HITL interrupt (one paused subagent). */
export interface PendingInterruptState {
	/** Stable id keyed by the parent ``tool_call_id`` stamped on the interrupt. */
	interruptId: string;
	threadId: number;
	assistantMsgId: string;
	interruptData: Record<string, unknown>;
	bundleToolCallIds: string[];
}

export interface PendingInterruptValue {
	/**
	 * Every paused subagent for the current turn, in the order the SSE stream
	 * delivered them — which matches ``state.interrupts`` traversal on the
	 * backend, which is the order ``slice_decisions_by_tool_call`` consumes.
	 */
	pendingInterrupts: PendingInterruptState[];
	/**
	 * Stage one card's decisions. The orchestrator (page-level) batches across
	 * cards and dispatches the resume only once every pending interrupt has
	 * submitted, so the backend slicer sees a single concatenated decisions
	 * list whose total matches the parent state's pending action count.
	 */
	onSubmit: (interruptId: string, decisions: HitlDecision[]) => void;
}

const PendingInterruptContext = createContext<PendingInterruptValue | null>(null);

/**
 * Bridges page-level interrupt state to the Timeline, which is mounted
 * by assistant-ui and can't be prop-drilled. Mount once at the chat
 * page root.
 */
export function PendingInterruptProvider({
	pendingInterrupts,
	onSubmit,
	children,
}: {
	pendingInterrupts: PendingInterruptState[];
	onSubmit: (interruptId: string, decisions: HitlDecision[]) => void;
	children: ReactNode;
}) {
	return (
		<PendingInterruptContext.Provider value={{ pendingInterrupts, onSubmit }}>
			{children}
		</PendingInterruptContext.Provider>
	);
}

export function usePendingInterrupt(): PendingInterruptValue | null {
	return useContext(PendingInterruptContext);
}
