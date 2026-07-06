"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useAtomValue } from "jotai";
import { AlarmClock, AlertCircle, CornerDownLeftIcon, ExternalLink, Pencil } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
	AutomationModelFields,
	type AutomationModelSelection,
} from "@/app/dashboard/[workspace_id]/automations/components/builder/automation-model-fields";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { JsonView } from "@/components/json-view";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { automationCreateRequest } from "@/contracts/types/automation.types";
import type { HitlDecision, InterruptResult } from "@/features/chat-messages/hitl";
import { isInterruptResult, useHitlDecision, useHitlPhase } from "@/features/chat-messages/hitl";
import { useAutomationEligibleModels } from "@/hooks/use-automation-eligible-models";
import {
	trackAutomationChatApproved,
	trackAutomationChatCreateFailed,
	trackAutomationChatCreateSucceeded,
	trackAutomationChatDraftEdited,
	trackAutomationChatRejected,
} from "@/lib/posthog/events";
import { AutomationDraftPreview } from "./automation-draft-preview";

const editArgsSchema = automationCreateRequest.omit({ workspace_id: true });

// ----------------------------------------------------------------------------
// Result discrimination — mirrors the backend return shapes in
// app/agents/multi_agent_chat/main_agent/tools/automation/create.py.
// ----------------------------------------------------------------------------

type AutomationCreateContext = {
	workspace_id?: number;
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
// Edit toggle reuses the same primitives as the Create-via-JSON page: raw
// textarea, Format, Zod validation against ``AutomationCreate`` (minus the
// ``workspace_id`` field, which the backend injects). Approve dispatches
// an ``edit`` decision with the parsed args when edits are pending, otherwise
// a plain ``approve``. Multi-turn chat refinement still works as a fallback.
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
	const canEdit = allowedDecisions.includes("edit");

	const [pendingEdits, setPendingEdits] = useState<Record<string, unknown> | null>(null);
	const [isEditing, setIsEditing] = useState(false);

	const effectiveArgs = pendingEdits ?? args;
	const draft = useMemo(() => extractDraft(effectiveArgs), [effectiveArgs]);

	// Per-automation model selection. The card always supplies models (chosen
	// here, not snapshotted from the search space), so Approve dispatches an
	// `edit` decision carrying `definition.models`.
	const searchSpaceId = useAtomValue(activeWorkspaceIdAtom);
	const eligibleModels = useAutomationEligibleModels();
	const [modelSelection, setModelSelection] = useState<AutomationModelSelection>({
		chatModelId: 0,
		imageConfigId: 0,
		visionConfigId: 0,
	});
	// Resolve each slot during render: an explicit pick wins, else the eligible
	// default. No effect seeds async hook data into state.
	const resolvedModels = useMemo<AutomationModelSelection>(
		() => ({
			chatModelId: modelSelection.chatModelId || eligibleModels.llm.defaultId || 0,
			imageConfigId: modelSelection.imageConfigId || eligibleModels.image.defaultId || 0,
			visionConfigId: modelSelection.visionConfigId || eligibleModels.vision.defaultId || 0,
		}),
		[
			modelSelection,
			eligibleModels.llm.defaultId,
			eligibleModels.image.defaultId,
			eligibleModels.vision.defaultId,
		]
	);
	const modelsResolved =
		resolvedModels.chatModelId !== 0 &&
		resolvedModels.imageConfigId !== 0 &&
		resolvedModels.visionConfigId !== 0;

	const handleApprove = useCallback(() => {
		if (phase !== "pending" || !canApprove || isEditing || !modelsResolved) return;
		setProcessing();
		const baseArgs = pendingEdits ?? args;
		const baseDefinition = (baseArgs.definition ?? {}) as Record<string, unknown>;
		const mergedArgs = {
			...baseArgs,
			definition: {
				...baseDefinition,
				models: {
					chat_model_id: resolvedModels.chatModelId,
					image_gen_model_id: resolvedModels.imageConfigId,
					vision_model_id: resolvedModels.visionConfigId,
				},
			},
		};
		const plan = Array.isArray(baseDefinition.plan) ? baseDefinition.plan : [];
		const triggers = Array.isArray(baseArgs.triggers) ? baseArgs.triggers : [];
		trackAutomationChatApproved({
			workspace_id: searchSpaceId ? Number(searchSpaceId) : undefined,
			edited: pendingEdits !== null,
			task_count: plan.length,
			trigger_type:
				(triggers[0] as { type?: string } | undefined)?.type ??
				(triggers.length ? undefined : "none"),
			chat_model_id: resolvedModels.chatModelId,
			image_gen_model_id: resolvedModels.imageConfigId,
			vision_model_id: resolvedModels.visionConfigId,
		});
		onDecision({
			type: "edit",
			edited_action: {
				name: interruptData.action_requests[0]?.name ?? "create_automation",
				args: mergedArgs,
			},
		});
	}, [
		phase,
		canApprove,
		isEditing,
		modelsResolved,
		setProcessing,
		onDecision,
		interruptData,
		args,
		pendingEdits,
		resolvedModels,
		searchSpaceId,
	]);

	const handleReject = useCallback(() => {
		if (phase !== "pending" || !canReject || isEditing) return;
		setRejected();
		trackAutomationChatRejected({
			workspace_id: searchSpaceId ? Number(searchSpaceId) : undefined,
		});
		onDecision({ type: "reject", message: "User rejected the automation draft." });
	}, [phase, canReject, isEditing, setRejected, onDecision, searchSpaceId]);

	useEffect(() => {
		if (isEditing) return;
		const handler = (e: KeyboardEvent) => {
			if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
				handleApprove();
			}
		};
		window.addEventListener("keydown", handler);
		return () => window.removeEventListener("keydown", handler);
	}, [handleApprove, isEditing]);

	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 transition-[box-shadow] duration-300">
			<div className="flex items-start justify-between gap-3 px-5 pt-5 pb-4 select-none">
				<div className="flex items-start gap-3 min-w-0">
					<AlarmClock className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" aria-hidden />
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
							<TextShimmerLoader
								text={pendingEdits ? "Saving with your edits" : "Saving automation"}
								size="sm"
							/>
						) : phase === "complete" ? (
							<p className="text-xs text-muted-foreground mt-0.5">
								{pendingEdits
									? "Automation saved with your edits"
									: "Automation created from this draft"}
							</p>
						) : phase === "rejected" ? (
							<p className="text-xs text-muted-foreground mt-0.5">
								No automation was saved — ask in chat to refine and try again.
							</p>
						) : (
							<p className="text-xs text-muted-foreground mt-0.5">
								{pendingEdits
									? "Showing your edits. Approve to save, or edit again."
									: "Review and approve to save. Edit for fine-tuning, or reply in chat for a redraft."}
							</p>
						)}
					</div>
				</div>
				{phase === "pending" && canEdit && !isEditing && (
					<Button
						size="sm"
						variant="ghost"
						className="rounded-lg text-muted-foreground -mt-1 -mr-2 shrink-0"
						onClick={() => setIsEditing(true)}
					>
						<Pencil className="size-3.5" />
						Edit
					</Button>
				)}
			</div>

			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				{isEditing ? (
					<JsonEditor
						initialValue={effectiveArgs}
						onSave={(parsed) => {
							setPendingEdits(parsed);
							setIsEditing(false);
							trackAutomationChatDraftEdited({
								workspace_id: searchSpaceId ? Number(searchSpaceId) : undefined,
							});
						}}
						onCancel={() => setIsEditing(false)}
					/>
				) : (
					<AutomationDraftPreview draft={draft} raw={effectiveArgs} />
				)}
			</div>

			{phase === "pending" && !isEditing && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4">
						<p className="mb-3 text-xs font-medium text-foreground">Models</p>
						<AutomationModelFields
							searchSpaceId={Number(searchSpaceId)}
							value={resolvedModels}
							onChange={(patch) => setModelSelection((prev) => ({ ...prev, ...patch }))}
						/>
					</div>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 flex items-center gap-2 select-none">
						{canApprove && (
							<Button
								size="sm"
								className="rounded-lg gap-1.5"
								disabled={!modelsResolved}
								onClick={handleApprove}
							>
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

interface JsonEditorProps {
	initialValue: Record<string, unknown>;
	onSave: (parsed: Record<string, unknown>) => void;
	onCancel: () => void;
}

function JsonEditor({ initialValue, onSave, onCancel }: JsonEditorProps) {
	const [value, setValue] = useState<Record<string, unknown>>(initialValue);
	const [issues, setIssues] = useState<string[]>([]);

	function handleSave() {
		setIssues([]);
		const result = editArgsSchema.safeParse(value);
		if (!result.success) {
			setIssues(
				result.error.issues.map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`)
			);
			return;
		}
		onSave(result.data as unknown as Record<string, unknown>);
	}

	return (
		<div className="space-y-3">
			<div className="rounded-md border border-input bg-background px-3 py-2 max-h-[24rem] overflow-auto">
				<JsonView
					src={value}
					editable
					onChange={(next) => setValue(next as Record<string, unknown>)}
					collapsed={false}
				/>
			</div>
			{issues.length > 0 && (
				<Alert variant="destructive">
					<AlertCircle aria-hidden />
					<AlertTitle>
						{issues.length} issue{issues.length === 1 ? "" : "s"}
					</AlertTitle>
					<AlertDescription>
						<ul className="list-inside list-disc">
							{issues.map((issue) => (
								<li key={issue} className="font-mono">
									{issue}
								</li>
							))}
						</ul>
					</AlertDescription>
				</Alert>
			)}
			<div className="flex items-center justify-end gap-2">
				<Button type="button" variant="ghost" size="sm" onClick={onCancel}>
					Cancel
				</Button>
				<Button type="button" size="sm" onClick={handleSave}>
					Save edits
				</Button>
			</div>
		</div>
	);
}

// ----------------------------------------------------------------------------
// Terminal result cards.
// ----------------------------------------------------------------------------

function SavedCard({ result }: { result: SavedResult }) {
	const searchSpaceId = useAtomValue(activeWorkspaceIdAtom);
	const tracked = useRef(false);
	useEffect(() => {
		if (tracked.current) return;
		tracked.current = true;
		trackAutomationChatCreateSucceeded({
			automation_id: result.automation_id,
			name: result.name,
			workspace_id: searchSpaceId ? Number(searchSpaceId) : undefined,
		});
	}, [result.automation_id, result.name, searchSpaceId]);

	const detailHref = searchSpaceId
		? `/dashboard/${searchSpaceId}/automations/${result.automation_id}`
		: null;

	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="flex items-start gap-3 px-5 pt-5 pb-4">
				<AlarmClock className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" aria-hidden />
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
	const searchSpaceId = useAtomValue(activeWorkspaceIdAtom);
	const tracked = useRef(false);
	useEffect(() => {
		if (tracked.current) return;
		tracked.current = true;
		trackAutomationChatCreateFailed({
			reason: "invalid",
			issue_count: result.issues.length,
			workspace_id: searchSpaceId ? Number(searchSpaceId) : undefined,
		});
	}, [result.issues.length, searchSpaceId]);

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
	const searchSpaceId = useAtomValue(activeWorkspaceIdAtom);
	const tracked = useRef(false);
	useEffect(() => {
		if (tracked.current) return;
		tracked.current = true;
		trackAutomationChatCreateFailed({
			reason: "error",
			message: result.message,
			workspace_id: searchSpaceId ? Number(searchSpaceId) : undefined,
		});
	}, [result.message, searchSpaceId]);

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
 * ``workspace_id`` which is injected server-side), so we trust the
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
