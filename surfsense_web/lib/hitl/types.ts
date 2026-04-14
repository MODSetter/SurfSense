/**
 * Shared types for Human-in-the-Loop (HITL) approval across all tools.
 *
 * Every tool-ui component that handles interrupts should import from here
 * instead of defining its own `InterruptResult` / `isInterruptResult`.
 */

export interface InterruptActionRequest {
	name: string;
	args: Record<string, unknown>;
}

export interface InterruptReviewConfig {
	action_name: string;
	allowed_decisions: Array<"approve" | "edit" | "reject">;
}

export interface InterruptResult<C extends Record<string, unknown> = Record<string, unknown>> {
	__interrupt__: true;
	__decided__?: "approve" | "reject" | "edit";
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
	type: "approve" | "reject" | "edit";
	message?: string;
	edited_action?: {
		name: string;
		args: Record<string, unknown>;
	};
}
