import type { ReactNode } from "react";

export interface InterruptActionRequest {
	name: string;
	args: Record<string, unknown>;
}

export interface InterruptReviewConfig {
	action_name: string;
	allowed_decisions: Array<"approve" | "edit" | "reject" | "approve_always">;
}

export interface InterruptResult<C extends Record<string, unknown> = Record<string, unknown>> {
	__interrupt__: true;
	__decided__?: "approve" | "reject" | "edit" | "approve_always";
	__completed__?: boolean;
	action_requests: InterruptActionRequest[];
	review_configs: InterruptReviewConfig[];
	interrupt_type?: string;
	context?: C;
	message?: string;
}

export function isInterruptResult(result: unknown): result is InterruptResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"__interrupt__" in result &&
		(result as InterruptResult).__interrupt__ === true
	);
}

export interface HitlDecision {
	type: "approve" | "reject" | "edit" | "approve_always";
	message?: string;
	edited_action?: {
		name: string;
		args: Record<string, unknown>;
	};
}

export type HitlPhase = "pending" | "processing" | "complete" | "rejected";

export interface PerToolApprovalCardProps {
	toolName: string;
	toolCallId: string;
	args: Record<string, unknown>;
	result: InterruptResult;
}

/**
 * Type signature for per-tool fallback approval cards (e.g.
 * ``GenericHitlApproval``, ``DoomLoopApproval``) mounted by
 * ``FallbackToolBody`` for unregistered HITL tools.
 *
 * Distinct from ``HitlApprovalCard`` (the high-level multi/single
 * chrome) — this is the per-tool body that the chrome wraps.
 */
export type PerToolApprovalCard = (props: PerToolApprovalCardProps) => ReactNode;
