"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useSetAtom } from "jotai";
import { CornerDownLeftIcon, Pen } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { openHitlEditPanelAtom } from "@/atoms/chat/hitl-edit-panel.atom";
import { PlateEditor } from "@/components/editor/plate-editor";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useHitlPhase } from "@/hooks/use-hitl-phase";
import { isInterruptResult, useHitlDecision } from "@/lib/hitl";
import type { InterruptResult, HitlDecision } from "@/lib/hitl";

interface LinearLabel {
	id: string;
	name: string;
	color: string;
}

interface LinearState {
	id: string;
	name: string;
	type: string;
	color: string;
}

interface LinearMember {
	id: string;
	name: string;
	displayName: string;
	email: string;
	active: boolean;
}

interface LinearPriority {
	priority: number;
	label: string;
}

interface LinearUpdateIssueContext {
	workspace?: { id: number; organization_name: string };
	priorities?: LinearPriority[];
	issue?: {
		id: string;
		identifier: string;
		title: string;
		description?: string;
		priority: number;
		url: string;
		current_state?: LinearState;
		current_assignee?: { id: string; name: string; email: string } | null;
		current_labels?: LinearLabel[];
		team_id: string;
		document_id: number;
	};
	team?: {
		id: string;
		name: string;
		key: string;
		states: LinearState[];
		members: LinearMember[];
		labels: LinearLabel[];
	};
	error?: string;
}

interface SuccessResult {
	status: "success";
	identifier: string;
	url: string;
	message?: string;
}

interface ErrorResult {
	status: "error";
	message: string;
}

interface NotFoundResult {
	status: "not_found";
	message: string;
}

interface AuthErrorResult {
	status: "auth_error";
	message: string;
	connector_id?: number;
	connector_type: string;
}

type UpdateLinearIssueResult =
	| InterruptResult<LinearUpdateIssueContext>
	| SuccessResult
	| ErrorResult
	| NotFoundResult
	| AuthErrorResult;

function isErrorResult(result: unknown): result is ErrorResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as ErrorResult).status === "error"
	);
}

function isNotFoundResult(result: unknown): result is NotFoundResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as NotFoundResult).status === "not_found"
	);
}

function isAuthErrorResult(result: unknown): result is AuthErrorResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as AuthErrorResult).status === "auth_error"
	);
}

function ApprovalCard({
	args,
	interruptData,
	onDecision,
}: {
	args: {
		issue_ref: string;
		new_title?: string;
		new_description?: string;
		new_state_name?: string;
		new_assignee_email?: string;
		new_priority?: number;
		new_label_names?: string[];
	};
	interruptData: InterruptResult<LinearUpdateIssueContext>;
	onDecision: (decision: HitlDecision) => void;
}) {
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);

	const actionArgs = interruptData.action_requests[0]?.args ?? {};
	const context = interruptData.context;
	const team = context?.team;
	const priorities = context?.priorities ?? [];
	const issue = context?.issue;

	const [isPanelOpen, setIsPanelOpen] = useState(false);
	const [editedArgs, setEditedArgs] = useState(() => ({
		title: actionArgs.new_title
			? String(actionArgs.new_title)
			: (issue?.title ?? args.new_title ?? ""),
		description: actionArgs.new_description
			? String(actionArgs.new_description)
			: (issue?.description ?? args.new_description ?? ""),
		stateId: actionArgs.new_state_id
			? String(actionArgs.new_state_id)
			: (issue?.current_state?.id ?? "__none__"),
		assigneeId: actionArgs.new_assignee_id
			? String(actionArgs.new_assignee_id)
			: (issue?.current_assignee?.id ?? "__none__"),
		priority:
			actionArgs.new_priority != null
				? String(actionArgs.new_priority)
				: String(issue?.priority ?? 0),
		labelIds: Array.isArray(actionArgs.new_label_ids)
			? (actionArgs.new_label_ids as string[])
			: (issue?.current_labels?.map((l) => l.id) ?? []),
	}));
	const [hasPanelEdits, setHasPanelEdits] = useState(false);
	const openHitlEditPanel = useSetAtom(openHitlEditPanelAtom);

	const reviewConfig = interruptData.review_configs[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	function resolveStateName(stateId: string | null) {
		if (!stateId || stateId === "__none__") return null;
		return team?.states.find((s) => s.id === stateId)?.name ?? stateId;
	}

	function resolveAssigneeName(assigneeId: string | null) {
		if (!assigneeId || assigneeId === "__none__") return null;
		const m = team?.members.find((m) => m.id === assigneeId);
		return m ? `${m.name} (${m.email})` : assigneeId;
	}

	function resolvePriorityLabel(p: string | null) {
		if (!p || p === "__none__") return null;
		return priorities.find((pr) => String(pr.priority) === p)?.label ?? p;
	}

	function resolveLabelNames(ids: string[]) {
		return ids.map((id) => team?.labels.find((l) => l.id === id)).filter(Boolean) as LinearLabel[];
	}

	const buildFinalArgs = useCallback(() => {
		const labelsWereProposed = Array.isArray(actionArgs.new_label_ids);
		return {
			issue_id: issue?.id,
			document_id: issue?.document_id,
			connector_id: context?.workspace?.id,
			new_title: editedArgs.title || null,
			new_description: editedArgs.description || null,
			new_state_id: editedArgs.stateId === "__none__" ? null : editedArgs.stateId,
			new_assignee_id: editedArgs.assigneeId === "__none__" ? null : editedArgs.assigneeId,
			new_priority: Number(editedArgs.priority),
			new_label_ids:
				labelsWereProposed || editedArgs.labelIds.length > 0 ? editedArgs.labelIds : null,
		};
	}, [actionArgs.new_label_ids, issue?.id, issue?.document_id, context?.workspace?.id, editedArgs]);

	const proposedStateName = resolveStateName(
		actionArgs.new_state_id ? String(actionArgs.new_state_id) : null
	);
	const proposedAssigneeName = resolveAssigneeName(
		actionArgs.new_assignee_id ? String(actionArgs.new_assignee_id) : null
	);
	const proposedPriorityLabel = resolvePriorityLabel(
		actionArgs.new_priority != null ? String(actionArgs.new_priority) : null
	);
	const proposedLabelObjects = resolveLabelNames(
		Array.isArray(actionArgs.new_label_ids) ? (actionArgs.new_label_ids as string[]) : []
	);

	const hasProposedChanges =
		actionArgs.new_title ||
		args.new_title ||
		actionArgs.new_description ||
		args.new_description ||
		proposedStateName ||
		proposedAssigneeName ||
		proposedPriorityLabel ||
		proposedLabelObjects.length > 0;

	const handleApprove = useCallback(() => {
		if (phase !== "pending") return;
		if (isPanelOpen) return;
		if (!allowedDecisions.includes("approve")) return;
		const isEdited = hasPanelEdits;
		setProcessing();
		onDecision({
			type: isEdited ? "edit" : "approve",
			edited_action: {
				name: interruptData.action_requests[0].name,
				args: buildFinalArgs(),
			},
		});
	}, [
		phase,
		setProcessing,
		isPanelOpen,
		allowedDecisions,
		onDecision,
		interruptData,
		buildFinalArgs,
		hasPanelEdits,
	]);

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
			{/* Header */}
			<div className="flex items-start justify-between px-5 pt-5 pb-4 select-none">
				<div>
					<p className="text-sm font-semibold text-foreground">
						{phase === "rejected"
							? "Linear Issue Update Rejected"
							: phase === "processing" || phase === "complete"
								? "Linear Issue Update Approved"
								: "Update Linear Issue"}
					</p>
					{phase === "processing" ? (
						<TextShimmerLoader
							text={hasPanelEdits ? "Updating issue with your changes" : "Updating issue"}
							size="sm"
						/>
					) : phase === "complete" ? (
						<p className="text-xs text-muted-foreground mt-0.5">
							{hasPanelEdits ? "Issue updated with your changes" : "Issue updated"}
						</p>
					) : phase === "rejected" ? (
						<p className="text-xs text-muted-foreground mt-0.5">Issue update was cancelled</p>
					) : (
						<p className="text-xs text-muted-foreground mt-0.5">
							Requires your approval to proceed
						</p>
					)}
				</div>
				{phase === "pending" && canEdit && (
					<Button
						size="sm"
						variant="ghost"
						className="rounded-lg text-muted-foreground -mt-1 -mr-2"
						onClick={() => {
							setIsPanelOpen(true);
							openHitlEditPanel({
								title: editedArgs.title,
								content: editedArgs.description,
								toolName: "Linear Issue",
								onSave: (newTitle, newDescription) => {
									setIsPanelOpen(false);
									setEditedArgs((prev) => ({
										...prev,
										title: newTitle,
										description: newDescription,
									}));
									setHasPanelEdits(true);
								},
								onClose: () => setIsPanelOpen(false),
							});
						}}
					>
						<Pen className="size-3.5" />
						Edit
					</Button>
				)}
			</div>

			{/* Context section — workspace + current issue + pickers in pending */}
			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 space-y-4 select-none">
						{context?.error ? (
							<p className="text-sm text-destructive">{context.error}</p>
						) : (
							<>
								{context?.workspace && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">Linear Account</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm">
											{context.workspace.organization_name}
										</div>
									</div>
								)}

								{issue && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">Current Issue</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm space-y-1.5">
											<div className="font-medium">
												{issue.identifier}: {issue.title}
											</div>
											<div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
												{issue.current_state && (
													<Badge
														className="rounded-full border-0"
														style={{
															backgroundColor: `${issue.current_state.color}22`,
															color: issue.current_state.color,
														}}
													>
														{issue.current_state.name}
													</Badge>
												)}
												{issue.current_assignee && <span>{issue.current_assignee.name}</span>}
												{priorities.find((p) => p.priority === issue.priority) && (
													<span>
														{priorities.find((p) => p.priority === issue.priority)?.label}
													</span>
												)}
											</div>
											{issue.current_labels && issue.current_labels.length > 0 && (
												<div className="flex flex-wrap gap-1">
													{issue.current_labels.map((label) => (
														<Badge
															key={label.id}
															className="rounded-full border-0 gap-1"
															style={{
																backgroundColor: `${label.color}22`,
																color: label.color,
															}}
														>
															{label.name}
														</Badge>
													))}
												</div>
											)}
											{issue.url && (
												<a
													href={issue.url}
													target="_blank"
													rel="noopener noreferrer"
													className="text-xs text-primary hover:underline"
												>
													Open in Linear ↗
												</a>
											)}
										</div>
									</div>
								)}

								{team && (
									<>
										<div className="space-y-2">
											<p className="text-xs font-medium text-muted-foreground">State</p>
											<Select
												value={editedArgs.stateId}
												onValueChange={(v) => setEditedArgs({ ...editedArgs, stateId: v })}
											>
												<SelectTrigger className="w-full">
													<SelectValue placeholder="Select state" />
												</SelectTrigger>
												<SelectContent>
													{team.states.map((s) => (
														<SelectItem key={s.id} value={s.id}>
															{s.name}
														</SelectItem>
													))}
												</SelectContent>
											</Select>
										</div>

										<div className="space-y-2">
											<p className="text-xs font-medium text-muted-foreground">Assignee</p>
											<Select
												value={editedArgs.assigneeId}
												onValueChange={(v) => setEditedArgs({ ...editedArgs, assigneeId: v })}
											>
												<SelectTrigger className="w-full">
													<SelectValue placeholder="Select assignee" />
												</SelectTrigger>
												<SelectContent>
													<SelectItem value="__none__">Unassigned</SelectItem>
													{team.members
														.filter((m) => m.active)
														.map((m) => (
															<SelectItem key={m.id} value={m.id}>
																{m.name} ({m.email})
															</SelectItem>
														))}
												</SelectContent>
											</Select>
										</div>

										<div className="space-y-2">
											<p className="text-xs font-medium text-muted-foreground">Priority</p>
											<Select
												value={editedArgs.priority}
												onValueChange={(v) => setEditedArgs({ ...editedArgs, priority: v })}
											>
												<SelectTrigger className="w-full">
													<SelectValue placeholder="Select priority" />
												</SelectTrigger>
												<SelectContent>
													{priorities.map((p) => (
														<SelectItem key={p.priority} value={String(p.priority)}>
															{p.label}
														</SelectItem>
													))}
												</SelectContent>
											</Select>
										</div>

										{team.labels.length > 0 && (
											<div className="space-y-2">
												<p className="text-xs font-medium text-muted-foreground">Labels</p>
												<ToggleGroup
													type="multiple"
													value={editedArgs.labelIds}
													onValueChange={(value) =>
														setEditedArgs({ ...editedArgs, labelIds: value })
													}
													className="flex flex-wrap gap-1.5"
												>
													{team.labels.map((label) => {
														const isSelected = editedArgs.labelIds.includes(label.id);
														return (
															<ToggleGroupItem
																key={label.id}
																value={label.id}
																className="h-auto rounded-full border-0 px-0 py-0 shadow-none hover:bg-transparent data-[state=on]:bg-transparent"
															>
																<Badge
																	className={`cursor-pointer rounded-full gap-1 border transition-all ${
																		isSelected
																			? "font-semibold opacity-100 shadow-sm"
																			: "border-transparent opacity-55 hover:opacity-90"
																	}`}
																	style={{
																		backgroundColor: isSelected
																			? `${label.color}70`
																			: `${label.color}28`,
																		color: label.color,
																		borderColor: isSelected ? `${label.color}cc` : "transparent",
																	}}
																>
																	<span
																		className="size-1.5 rounded-full"
																		style={{ backgroundColor: label.color }}
																	/>
																	{label.name}
																</Badge>
															</ToggleGroupItem>
														);
													})}
												</ToggleGroup>
											</div>
										)}
									</>
								)}
							</>
						)}
					</div>
				</>
			)}

			{/* Content preview — proposed changes */}
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 pt-3">
				{hasProposedChanges || hasPanelEdits ? (
					<>
						{(hasPanelEdits ? editedArgs.title : (actionArgs.new_title ?? args.new_title)) && (
							<p className="text-sm font-medium text-foreground">
								{String(
									hasPanelEdits ? editedArgs.title : (actionArgs.new_title ?? args.new_title)
								)}
							</p>
						)}
						{(hasPanelEdits
							? editedArgs.description
							: (actionArgs.new_description ?? args.new_description)) && (
							<div
								className="max-h-[7rem] overflow-hidden text-sm"
								style={{
									maskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
									WebkitMaskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
								}}
							>
								<PlateEditor
									markdown={String(
										hasPanelEdits
											? editedArgs.description
											: (actionArgs.new_description ?? args.new_description)
									)}
									readOnly
									preset="readonly"
									editorVariant="none"
									className="h-auto [&_[data-slate-editor]]:!min-h-0 [&_[data-slate-editor]>*:first-child]:!mt-0"
								/>
							</div>
						)}
						{proposedStateName && (
							<div className="mt-2">
								<span className="text-xs text-muted-foreground">State → </span>
								<span className="text-xs font-medium">{proposedStateName}</span>
							</div>
						)}
						{proposedAssigneeName && (
							<div className="mt-1">
								<span className="text-xs text-muted-foreground">Assignee → </span>
								<span className="text-xs font-medium">{proposedAssigneeName}</span>
							</div>
						)}
						{proposedPriorityLabel && (
							<div className="mt-1">
								<span className="text-xs text-muted-foreground">Priority → </span>
								<span className="text-xs font-medium">{proposedPriorityLabel}</span>
							</div>
						)}
						{proposedLabelObjects.length > 0 && (
							<div className="flex flex-wrap gap-1 mt-2">
								{proposedLabelObjects.map((label) => (
									<Badge
										key={label.id}
										className="rounded-full border-0 gap-1"
										style={{
											backgroundColor: `${label.color}33`,
											color: label.color,
										}}
									>
										{label.name}
									</Badge>
								))}
							</div>
						)}
					</>
				) : (
					<p className="text-sm text-muted-foreground italic pb-3">No changes proposed</p>
				)}
			</div>

			{/* Action buttons - only shown when pending */}
			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 flex items-center gap-2 select-none">
						{allowedDecisions.includes("approve") && (
							<Button
								size="sm"
								className="rounded-lg gap-1.5"
								onClick={handleApprove}
								disabled={isPanelOpen}
							>
								Approve
								<CornerDownLeftIcon className="size-3 opacity-60" />
							</Button>
						)}
						{allowedDecisions.includes("reject") && (
							<Button
								size="sm"
								variant="ghost"
								className="rounded-lg text-muted-foreground"
								disabled={isPanelOpen}
								onClick={() => {
									setRejected();
									onDecision({ type: "reject", message: "User rejected the action." });
								}}
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

function AuthErrorCard({ result }: { result: AuthErrorResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">Linear authentication expired</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<p className="text-sm text-muted-foreground">{result.message}</p>
			</div>
		</div>
	);
}

function ErrorCard({ result }: { result: ErrorResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">Failed to update Linear issue</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<p className="text-sm text-muted-foreground">{result.message}</p>
			</div>
		</div>
	);
}

function NotFoundCard({ result }: { result: NotFoundResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-amber-600 dark:text-amber-400">Issue not found</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<p className="text-sm text-muted-foreground">{result.message}</p>
			</div>
		</div>
	);
}

function SuccessCard({ result }: { result: SuccessResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-foreground">
					{result.message || "Linear issue updated successfully"}
				</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4 space-y-2 text-xs">
				<div>
					<span className="font-medium text-muted-foreground">Identifier: </span>
					<span>{result.identifier}</span>
				</div>
				{result.url && (
					<div>
						<a
							href={result.url}
							target="_blank"
							rel="noopener noreferrer"
							className="text-primary hover:underline"
						>
							Open in Linear
						</a>
					</div>
				)}
			</div>
		</div>
	);
}

export const UpdateLinearIssueToolUI = ({
	args,
	result,
}: ToolCallMessagePartProps<
	{
		issue_ref: string;
		new_title?: string;
		new_description?: string;
		new_state_name?: string;
		new_assignee_email?: string;
		new_priority?: number;
		new_label_names?: string[];
	},
	UpdateLinearIssueResult
>) => {
	const { dispatch } = useHitlDecision();

	if (!result) return null;

	if (isInterruptResult(result)) {
		return (
			<ApprovalCard
				args={args}
				interruptData={result as InterruptResult<LinearUpdateIssueContext>}
				onDecision={(decision) => dispatch([decision])}
			/>
		);
	}

	if (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as { status: string }).status === "rejected"
	) {
		return null;
	}

	if (isNotFoundResult(result)) return <NotFoundCard result={result} />;
	if (isAuthErrorResult(result)) return <AuthErrorCard result={result} />;
	if (isErrorResult(result)) return <ErrorCard result={result} />;

	return <SuccessCard result={result as SuccessResult} />;
};
