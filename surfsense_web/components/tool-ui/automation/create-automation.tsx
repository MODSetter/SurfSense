"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useAtomValue } from "jotai";
import { CornerDownLeftIcon, ExternalLink, Workflow } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo } from "react";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import type { HitlDecision, InterruptResult } from "@/features/chat-messages/hitl";
import { isInterruptResult, useHitlDecision, useHitlPhase } from "@/features/chat-messages/hitl";
import { AutomationDraftPreview } from "./automation-draft-preview";

// ----------------------------------------------------------------------------
// Result discrimination — mirrors the backend return shapes in
// app/agents/multi_agent_chat/main_agent/tools/automation/create.py.
// ----------------------------------------------------------------------------

type AutomationCreateContext = {
	search_space_id?: number;
};

interface SavedResult {
	status: "saved";
	automation_id: number;
	name: string;
}

interface RejectedResult {
	status: "rejected";
	message?: string;
}

interface InvalidResult {
	status: "invalid";
	issues: string[];
	raw?: unknown;
}

interface ErrorResult {
	status: "error";
	message: string;
}

type CreateAutomationResult =
	| InterruptResult<AutomationCreateContext>
	| SavedResult
	| RejectedResult
	| InvalidResult
	| ErrorResult;

function hasStatus(value: unknown, status: string): boolean {
	return (
		typeof value === "object" &&
		value !== null &&
		"status" in value &&
		(value as { status: unknown }).status === status
	);
}

// ----------------------------------------------------------------------------
// Approval card — pending → processing → complete / rejected.
//
// v1 deliberately supports only approve/reject. The drafted JSON is complex
// (full plan + triggers) and we already have a multi-turn refinement path via
// chat ("make it run at 10am instead" → the agent re-calls the tool with a
// refined intent). An in-card edit form would duplicate that flow and add UX
// surface area we don't need yet — leave it for the raw-JSON path on the
// detail page.
// ----------------------------------------------------------------------------

interface ApprovalCardProps {
	args: Record<string, unknown>;
	interruptData: InterruptResult<AutomationCreateContext>;
	onDecision: (decision: HitlDecision) => void;
}

function ApprovalCard({ args, interruptData, onDecision }: ApprovalCardProps) {
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);

	const reviewConfig = interruptData.review_configs[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canApprove = allowedDecisions.includes("approve");
	const canReject = allowedDecisions.includes("reject");

	const draft = useMemo(() => extractDraft(args), [args]);

	const handleApprove = useCallback(() => {
		if (phase !== "pending" || !canApprove) return;
		setProcessing();
		onDecision({
			type: "approve",
			edited_action: {
				name: interruptData.action_requests[0]?.name ?? "create_automation",
				args,
			},
		});
	}, [phase, canApprove, setProcessing, onDecision, interruptData, args]);

	const handleReject = useCallback(() => {
		if (phase !== "pending" || !canReject) return;
		setRejected();
		onDecision({ type: "reject", message: "User rejected the automation draft." });
	}, [phase, canReject, setRejected, onDecision]);

	useEffect(() => {
		const handler = (e: KeyboardEvent) => {
			if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
				handleApprove();
			}
		};
		window.addEventListener("keydown", handler);
		return () => window.removeEventListener("keydown", handler);
	}, [handleApprove]);

	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 transition-[box-shadow] duration-300">
			<div className="flex items-start gap-3 px-5 pt-5 pb-4 select-none">
				<Workflow className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" aria-hidden />
				<div className="min-w-0">
					<p className="text-sm font-semibold text-foreground">
						{phase === "rejected"
							? "Automation cancelled"
							: phase === "processing"
								? "Saving automation"
								: phase === "complete"
									? "Automation saved"
									: "Create automation"}
					</p>
					{phase === "processing" ? (
						<TextShimmerLoader text="Saving automation" size="sm" />
					) : phase === "complete" ? (
						<p className="text-xs text-muted-foreground mt-0.5">
							Automation created from this draft
						</p>
					) : phase === "rejected" ? (
						<p className="text-xs text-muted-foreground mt-0.5">
							No automation was saved — ask in chat to refine and try again.
						</p>
					) : (
						<p className="text-xs text-muted-foreground mt-0.5">
							Review and approve to save. To change anything, reply in chat — I'll redraft.
						</p>
					)}
				</div>
			</div>

			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<AutomationDraftPreview draft={draft} raw={args} />
			</div>

			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 flex items-center gap-2 select-none">
						{canApprove && (
							<Button size="sm" className="rounded-lg gap-1.5" onClick={handleApprove}>
								Approve
								<CornerDownLeftIcon className="size-3 opacity-60" />
							</Button>
						)}
						{canReject && (
							<Button
								size="sm"
								variant="ghost"
								className="rounded-lg text-muted-foreground"
								onClick={handleReject}
							>
								Reject
							</Button>
						)}
					</div>
				</>
			)}
		</div>
	);
}

// ----------------------------------------------------------------------------
// Terminal result cards.
// ----------------------------------------------------------------------------

function SavedCard({ result }: { result: SavedResult }) {
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const detailHref = searchSpaceId
		? `/dashboard/${searchSpaceId}/automations/${result.automation_id}`
		: null;

	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="flex items-start gap-3 px-5 pt-5 pb-4">
				<Workflow className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" aria-hidden />
				<div className="min-w-0">
					<p className="text-sm font-semibold text-foreground">Automation saved</p>
					<p className="text-xs text-muted-foreground mt-0.5">{result.name}</p>
				</div>
			</div>
			{detailHref && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-3">
						<Link
							href={detailHref}
							className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
						>
							<ExternalLink className="h-3.5 w-3.5" aria-hidden />
							Open automation #{result.automation_id}
						</Link>
					</div>
				</>
			)}
		</div>
	);
}

function InvalidCard({ result }: { result: InvalidResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">Couldn't draft this automation</p>
				<p className="text-xs text-muted-foreground mt-0.5">
					The drafter produced output that didn't validate. I'll refine and retry.
				</p>
			</div>
			{result.issues.length > 0 && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<ul className="px-5 py-3 space-y-1 text-xs text-muted-foreground list-disc list-inside">
						{result.issues.map((issue) => (
							<li key={issue}>{issue}</li>
						))}
					</ul>
				</>
			)}
		</div>
	);
}

function ErrorCard({ result }: { result: ErrorResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">Failed to create automation</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<p className="text-sm text-muted-foreground">{result.message}</p>
			</div>
		</div>
	);
}

// ----------------------------------------------------------------------------
// Entry — dispatches between the approval card and terminal result cards.
//
// Rejection is special: we hide the standalone "rejected" card because the
// approval card itself already transitions to a "rejected" phase inline. A
// second message in the timeline would be noisy.
// ----------------------------------------------------------------------------

export const CreateAutomationToolUI = ({
	args,
	result,
}: ToolCallMessagePartProps<{ intent: string }, CreateAutomationResult>) => {
	const { dispatch } = useHitlDecision();

	if (!result) return null;

	if (isInterruptResult(result)) {
		return (
			<ApprovalCard
				args={args as unknown as Record<string, unknown>}
				interruptData={result as InterruptResult<AutomationCreateContext>}
				onDecision={(decision) => dispatch([decision])}
			/>
		);
	}

	if (hasStatus(result, "rejected")) return null;
	if (hasStatus(result, "saved")) return <SavedCard result={result as SavedResult} />;
	if (hasStatus(result, "invalid")) return <InvalidCard result={result as InvalidResult} />;
	if (hasStatus(result, "error")) return <ErrorCard result={result as ErrorResult} />;

	return null;
};

// ----------------------------------------------------------------------------
// Helpers.
// ----------------------------------------------------------------------------

/**
 * Project raw args into the shape ``AutomationDraftPreview`` expects.
 *
 * The args dict is the full ``AutomationCreate`` payload (minus
 * ``search_space_id`` which is injected server-side), so we trust the
 * top-level fields but defend against missing nested defaults.
 */
function extractDraft(args: Record<string, unknown>) {
	const definition = (args.definition ?? {}) as Record<string, unknown>;
	const planSteps = Array.isArray(definition.plan)
		? (definition.plan as Array<Record<string, unknown>>).map((step) => ({
				step_id: String(step.step_id ?? "(unnamed)"),
				action: String(step.action ?? ""),
				when: typeof step.when === "string" ? step.when : null,
			}))
		: [];

	const triggers = Array.isArray(args.triggers)
		? (args.triggers as Array<Record<string, unknown>>).map((trigger) => ({
				type: String(trigger.type ?? "schedule"),
				params: (trigger.params ?? {}) as Record<string, unknown>,
				static_inputs: (trigger.static_inputs ?? {}) as Record<string, unknown>,
				enabled: trigger.enabled !== false,
			}))
		: [];

	return {
		name: String(args.name ?? "(unnamed automation)"),
		description: typeof args.description === "string" ? args.description : null,
		definition: {
			goal: typeof definition.goal === "string" ? definition.goal : null,
			plan: planSteps,
		},
		triggers,
	};
}
