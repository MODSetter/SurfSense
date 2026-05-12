"use client";

import { createContext, type ReactNode, useContext } from "react";
import type { HitlDecision } from "../types";

/** Snapshot of one in-flight HITL interrupt; ``null`` when nothing is pending. */
export interface PendingInterruptState {
	threadId: number;
	assistantMsgId: string;
	interruptData: Record<string, unknown>;
	bundleToolCallIds: string[];
}

export interface PendingInterruptValue {
	pendingInterrupt: PendingInterruptState | null;
	onSubmit: (decisions: HitlDecision[]) => void;
}

const PendingInterruptContext = createContext<PendingInterruptValue | null>(null);

/**
 * Bridges page-level interrupt state to the Timeline, which is mounted
 * by assistant-ui and can't be prop-drilled. Mount once at the chat
 * page root.
 */
export function PendingInterruptProvider({
	pendingInterrupt,
	onSubmit,
	children,
}: {
	pendingInterrupt: PendingInterruptState | null;
	onSubmit: (decisions: HitlDecision[]) => void;
	children: ReactNode;
}) {
	return (
		<PendingInterruptContext.Provider value={{ pendingInterrupt, onSubmit }}>
			{children}
		</PendingInterruptContext.Provider>
	);
}

export function usePendingInterrupt(): PendingInterruptValue | null {
	return useContext(PendingInterruptContext);
}
