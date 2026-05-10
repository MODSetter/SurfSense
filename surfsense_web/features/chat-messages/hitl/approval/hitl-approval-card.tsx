"use client";

import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";
import { type FC, useCallback, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { getToolDisplayName } from "@/contracts/enums/toolIcons";
import {
	FallbackToolBody,
	getToolComponent,
	type TimelineToolProps,
} from "@/features/chat-messages/timeline/tool-registry";
import type {
	HitlDecision,
	InterruptActionRequest,
	InterruptResult,
	InterruptReviewConfig,
} from "../types";
import { type HitlApprovalAPI, HitlApprovalContext } from "./approval-context";
import type { PendingInterruptState } from "./pending-interrupt-context";

/**
 * Narrow the bundle interrupt to the active step so per-tool bodies
 * see the same single-action shape they're written against. Mirrors
 * any staged decision onto ``__decided__`` (and edited args onto
 * ``args``) so revisiting a decided step via Prev shows the past
 * choice instead of pristine Approve/Reject buttons.
 */
function sliceForStep(
	interruptData: Record<string, unknown>,
	action: InterruptActionRequest,
	reviewConfig: InterruptReviewConfig | undefined,
	stagedDecision: HitlDecision | undefined
): InterruptResult {
	const baseAction =
		stagedDecision?.type === "edit" && stagedDecision.edited_action
			? { ...action, args: stagedDecision.edited_action.args }
			: action;

	const sliced: InterruptResult = {
		...(interruptData as Partial<InterruptResult>),
		__interrupt__: true,
		action_requests: [baseAction],
		review_configs: reviewConfig ? [reviewConfig] : [],
	} as InterruptResult;

	if (stagedDecision) {
		(sliced as unknown as Record<string, unknown>).__decided__ = stagedDecision.type;
	}

	return sliced;
}

/**
 * Single chrome for every HITL approval flow. Branches on
 * ``action_requests.length``: 1 → per-tool body alone with auto-
 * submit on first decision; ≥2 → per-tool body + inline pager +
 * Submit-decisions (fires only once every step has a decision).
 * Decisions are positional to match the resume protocol.
 */
export const HitlApprovalCard: FC<{
	pendingInterrupt: PendingInterruptState;
	onSubmit: (decisions: HitlDecision[]) => void;
}> = ({ pendingInterrupt, onSubmit }) => {
	const interruptData = pendingInterrupt.interruptData as InterruptResult & Record<string, unknown>;
	const actionRequests = (interruptData.action_requests ?? []) as InterruptActionRequest[];
	const reviewConfigs = (interruptData.review_configs ?? []) as InterruptReviewConfig[];
	const total = actionRequests.length;
	const isMulti = total >= 2;

	const [currentStep, setCurrentStep] = useState(0);
	const [decisions, setDecisions] = useState<(HitlDecision | undefined)[]>(() =>
		Array.from({ length: total }, () => undefined)
	);

	// Reset on a new interrupt-request while still mounted (rapid
	// back-to-back resumes), otherwise stale decisions would leak.
	const [prevActionsRef, setPrevActionsRef] = useState(actionRequests);
	if (prevActionsRef !== actionRequests) {
		setPrevActionsRef(actionRequests);
		setCurrentStep(0);
		setDecisions(Array.from({ length: total }, () => undefined));
	}

	const submitFromDecisions = useCallback(
		(next: (HitlDecision | undefined)[]) => {
			if (next.length !== total) return;
			if (next.some((d) => d === undefined)) return;
			onSubmit(next as HitlDecision[]);
		},
		[onSubmit, total]
	);

	const stage = useCallback(
		(decision: HitlDecision) => {
			// Compute next array outside the setter so the side effect
			// (auto-submit / step advance) runs once under StrictMode.
			const updated = decisions.slice();
			updated[currentStep] = decision;
			setDecisions(updated);

			if (!isMulti) {
				submitFromDecisions(updated);
				return;
			}

			// Skip to the next undecided step rather than +1 so users
			// who jumped via Prev don't get pulled back to a decided
			// step.
			let target = currentStep;
			for (let i = currentStep + 1; i < updated.length; i++) {
				if (updated[i] === undefined) {
					target = i;
					break;
				}
			}
			if (target !== currentStep) setCurrentStep(target);
		},
		[currentStep, decisions, isMulti, submitFromDecisions]
	);

	const next = useCallback(() => {
		setCurrentStep((s) => Math.min(s + 1, Math.max(0, total - 1)));
	}, [total]);
	const prev = useCallback(() => {
		setCurrentStep((s) => Math.max(s - 1, 0));
	}, []);
	const goToStep = useCallback(
		(i: number) => {
			if (i < 0 || i >= total) return;
			setCurrentStep(i);
		},
		[total]
	);
	const submit = useCallback(() => {
		submitFromDecisions(decisions);
	}, [decisions, submitFromDecisions]);

	const stagedCount = useMemo(() => decisions.filter((d) => d !== undefined).length, [decisions]);
	const canSubmit = stagedCount === total && total > 0;
	const canAdvance = decisions[currentStep] !== undefined;

	const api = useMemo<HitlApprovalAPI>(
		() => ({
			total,
			currentStep,
			decisions,
			stage,
			next,
			prev,
			goToStep,
			canAdvance,
			canSubmit,
		}),
		[total, currentStep, decisions, stage, next, prev, goToStep, canAdvance, canSubmit]
	);

	if (total === 0) return null;

	const action = actionRequests[currentStep];
	const reviewConfig = reviewConfigs[currentStep];
	const stagedDecision = decisions[currentStep];
	const sliced = sliceForStep(interruptData, action, reviewConfig, stagedDecision);

	const Body = getToolComponent(action.name) ?? FallbackToolBody;
	const bodyProps: TimelineToolProps = {
		// Per-step key remounts the body on navigation so per-tool
		// internal state (useHitlPhase, edit drafts) doesn't bleed
		// between steps.
		toolCallId: pendingInterrupt.bundleToolCallIds[currentStep] ?? `step-${currentStep}`,
		toolName: action.name,
		args: (sliced.action_requests[0]?.args ?? {}) as Record<string, unknown>,
		argsText: undefined,
		result: sliced,
		langchainToolCallId: undefined,
		status: stagedDecision ? "completed" : "running",
	};

	return (
		<HitlApprovalContext.Provider value={api}>
			<div className="space-y-2">
				<div key={`approval-step-${currentStep}`}>
					<Body {...bodyProps} />
				</div>
				{isMulti && (
					<PagerBar
						currentStep={currentStep}
						total={total}
						stagedCount={stagedCount}
						canAdvance={canAdvance}
						canSubmit={canSubmit}
						actionName={action.name}
						onPrev={prev}
						onNext={next}
						onSubmit={submit}
					/>
				)}
			</div>
		</HitlApprovalContext.Provider>
	);
};

const PagerBar: FC<{
	currentStep: number;
	total: number;
	stagedCount: number;
	canAdvance: boolean;
	canSubmit: boolean;
	actionName: string;
	onPrev: () => void;
	onNext: () => void;
	onSubmit: () => void;
}> = ({
	currentStep,
	total,
	stagedCount,
	canAdvance,
	canSubmit,
	actionName,
	onPrev,
	onNext,
	onSubmit,
}) => (
	<div className="flex items-center gap-2 rounded-md border border-border bg-muted/40 px-2 py-1.5 text-sm">
		<Button
			type="button"
			size="sm"
			variant="outline"
			onClick={onPrev}
			disabled={currentStep === 0}
			aria-label="Previous approval"
		>
			<ChevronLeftIcon className="h-4 w-4" />
		</Button>
		<span className="font-medium tabular-nums">
			{currentStep + 1} / {total}
		</span>
		<span className="text-muted-foreground">·</span>
		<span className="text-muted-foreground">
			{stagedCount} of {total} decided
		</span>
		<Button
			type="button"
			size="sm"
			variant="outline"
			onClick={onNext}
			disabled={!canAdvance || currentStep >= total - 1}
			aria-label="Next approval"
			title={!canAdvance ? "Decide on this action first" : undefined}
		>
			<ChevronRightIcon className="h-4 w-4" />
		</Button>
		<span className="ml-2 truncate text-xs text-muted-foreground" title={actionName}>
			{getToolDisplayName(actionName)}
		</span>
		<div className="ml-auto">
			<Button
				type="button"
				size="sm"
				onClick={onSubmit}
				disabled={!canSubmit}
				title={canSubmit ? "Submit decisions" : "Decide every action first"}
			>
				Submit decisions
			</Button>
		</div>
	</div>
);
