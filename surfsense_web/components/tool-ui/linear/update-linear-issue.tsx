"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
	AlertTriangleIcon,
	CheckIcon,
	InfoIcon,
	Loader2Icon,
	PencilIcon,
	XIcon,
} from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

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

interface InterruptResult {
	__interrupt__: true;
	__decided__?: "approve" | "reject" | "edit";
	action_requests: Array<{
		name: string;
		args: Record<string, unknown>;
	}>;
	review_configs: Array<{
		action_name: string;
		allowed_decisions: Array<"approve" | "edit" | "reject">;
	}>;
	interrupt_type?: string;
	context?: {
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
	};
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

type UpdateLinearIssueResult = InterruptResult | SuccessResult | ErrorResult | NotFoundResult;

function isInterruptResult(result: unknown): result is InterruptResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"__interrupt__" in result &&
		(result as InterruptResult).__interrupt__ === true
	);
}

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

function ApprovalCard({
	interruptData,
	onDecision,
}: {
	interruptData: InterruptResult;
	onDecision: (decision: {
		type: "approve" | "reject" | "edit";
		message?: string;
		edited_action?: { name: string; args: Record<string, unknown> };
	}) => void;
}) {
	const actionArgs = interruptData.action_requests[0]?.args ?? {};
	const context = interruptData.context;
	const team = context?.team;
	const priorities = context?.priorities ?? [];
	const issue = context?.issue;

	const initialEditState = {
		title: actionArgs.new_title ? String(actionArgs.new_title) : (issue?.title ?? ""),
		description: actionArgs.new_description
			? String(actionArgs.new_description)
			: (issue?.description ?? ""),
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
	};

	const [decided, setDecided] = useState<"approve" | "reject" | "edit" | null>(
		interruptData.__decided__ ?? null
	);
	const [isEditing, setIsEditing] = useState(false);
	const [editedArgs, setEditedArgs] = useState(initialEditState);

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

	function buildFinalArgs() {
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
	}

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
		actionArgs.new_description ||
		proposedStateName ||
		proposedAssigneeName ||
		proposedPriorityLabel ||
		proposedLabelObjects.length > 0;

	return (
		<div
			className={`my-4 max-w-full overflow-hidden rounded-xl transition-all duration-300 ${
				decided
					? "border border-border bg-card shadow-sm"
					: "border-2 border-foreground/20 bg-muted/30 dark:bg-muted/10 shadow-lg animate-pulse-subtle"
			}`}
		>
			{/* Header */}
			<div
				className={`flex items-center gap-3 border-b ${
					decided ? "border-border bg-card" : "border-foreground/15 bg-muted/40 dark:bg-muted/20"
				} px-4 py-3`}
			>
				<div
					className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${
						decided ? "bg-muted" : "bg-muted animate-pulse"
					}`}
				>
					<AlertTriangleIcon
						className={`size-4 ${decided ? "text-muted-foreground" : "text-foreground"}`}
					/>
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-sm font-medium text-foreground">Update Linear Issue</p>
					<p className="truncate text-xs text-muted-foreground">
						{isEditing ? "You can edit the arguments below" : "Requires your approval to proceed"}
					</p>
				</div>
			</div>

			{/* Context section — workspace + current issue (read-only) */}
			{!decided && (
				<div className="border-b border-border px-4 py-3 bg-muted/30 space-y-3">
					{context?.error ? (
						<p className="text-sm text-destructive">{context.error}</p>
					) : (
						<>
							{context?.workspace && (
								<div className="space-y-1">
									<div className="text-xs font-medium text-muted-foreground">Linear Account</div>
									<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm">
										{context.workspace.organization_name}
									</div>
								</div>
							)}

							{issue && (
								<div className="space-y-1">
									<div className="text-xs font-medium text-muted-foreground">Current Issue</div>
									<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm space-y-1.5">
										<div className="font-medium">
											{issue.identifier}: {issue.title}
										</div>
										<div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
											{issue.current_state && (
												<span
													className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
													style={{
														backgroundColor: `${issue.current_state.color}22`,
														color: issue.current_state.color,
													}}
												>
													{issue.current_state.name}
												</span>
											)}
											{issue.current_assignee && <span>{issue.current_assignee.name}</span>}
											{priorities.find((p) => p.priority === issue.priority) && (
												<span>{priorities.find((p) => p.priority === issue.priority)?.label}</span>
											)}
										</div>
										{issue.current_labels && issue.current_labels.length > 0 && (
											<div className="flex flex-wrap gap-1">
												{issue.current_labels.map((label) => (
													<span
														key={label.id}
														className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
														style={{
															backgroundColor: `${label.color}22`,
															color: label.color,
														}}
													>
														{label.name}
													</span>
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
						</>
					)}
				</div>
			)}

			{/* Display mode — proposed changes */}
			{!isEditing && (
				<div className="space-y-2 px-4 py-3 bg-card">
					{hasProposedChanges ? (
						<>
							{actionArgs.new_title && (
								<div>
									<p className="text-xs font-medium text-muted-foreground">New Title</p>
									<p className="text-sm text-foreground">{String(actionArgs.new_title)}</p>
								</div>
							)}
							{actionArgs.new_description && (
								<div>
									<p className="text-xs font-medium text-muted-foreground">New Description</p>
									<p className="line-clamp-4 text-sm whitespace-pre-wrap text-foreground">
										{String(actionArgs.new_description)}
									</p>
								</div>
							)}
							{proposedStateName && (
								<div>
									<p className="text-xs font-medium text-muted-foreground">New State</p>
									<p className="text-sm text-foreground">{proposedStateName}</p>
								</div>
							)}
							{proposedAssigneeName && (
								<div>
									<p className="text-xs font-medium text-muted-foreground">New Assignee</p>
									<p className="text-sm text-foreground">{proposedAssigneeName}</p>
								</div>
							)}
							{proposedPriorityLabel && (
								<div>
									<p className="text-xs font-medium text-muted-foreground">New Priority</p>
									<p className="text-sm text-foreground">{proposedPriorityLabel}</p>
								</div>
							)}
							{proposedLabelObjects.length > 0 && (
								<div>
									<p className="text-xs font-medium text-muted-foreground">New Labels</p>
									<div className="flex flex-wrap gap-1 mt-1">
										{proposedLabelObjects.map((label) => (
											<span
												key={label.id}
												className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
												style={{
													backgroundColor: `${label.color}33`,
													color: label.color,
												}}
											>
												{label.name}
											</span>
										))}
									</div>
								</div>
							)}
						</>
					) : (
						<p className="text-sm text-muted-foreground italic">No changes proposed</p>
					)}
				</div>
			)}

			{/* Edit mode */}
			{isEditing && !decided && (
				<div className="space-y-3 px-4 py-3 bg-card">
					<div>
						<label
							htmlFor="linear-update-title"
							className="text-xs font-medium text-muted-foreground mb-1.5 block"
						>
							New Title
						</label>
						<Input
							id="linear-update-title"
							value={editedArgs.title}
							onChange={(e) => setEditedArgs({ ...editedArgs, title: e.target.value })}
							placeholder="Issue title"
						/>
					</div>

					<div>
						<label
							htmlFor="linear-update-description"
							className="text-xs font-medium text-muted-foreground mb-1.5 block"
						>
							Description
						</label>
						<Textarea
							id="linear-update-description"
							value={editedArgs.description}
							onChange={(e) => setEditedArgs({ ...editedArgs, description: e.target.value })}
							placeholder="Issue description"
							rows={5}
							className="resize-none"
						/>
					</div>

					{team && (
						<>
							<div className="space-y-1.5">
								<div className="text-xs font-medium text-muted-foreground">State</div>
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

							<div className="space-y-1.5">
								<div className="text-xs font-medium text-muted-foreground">Assignee</div>
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

							<div className="space-y-1.5">
								<div className="text-xs font-medium text-muted-foreground">Priority</div>
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
								<div className="space-y-1.5">
									<div className="text-xs font-medium text-muted-foreground">Labels</div>
									<div className="flex flex-wrap gap-1.5">
										{team.labels.map((label) => {
											const isSelected = editedArgs.labelIds.includes(label.id);
											return (
												<button
													key={label.id}
													type="button"
													onClick={() =>
														setEditedArgs({
															...editedArgs,
															labelIds: isSelected
																? editedArgs.labelIds.filter((id) => id !== label.id)
																: [...editedArgs.labelIds, label.id],
														})
													}
													className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium transition-opacity ${
														isSelected
															? "opacity-100 ring-2 ring-foreground/30"
															: "opacity-50 hover:opacity-80"
													}`}
													style={{
														backgroundColor: `${label.color}33`,
														color: label.color,
													}}
												>
													<span
														className="size-1.5 rounded-full"
														style={{ backgroundColor: label.color }}
													/>
													{label.name}
												</button>
											);
										})}
									</div>
								</div>
							)}
						</>
					)}
				</div>
			)}

			{/* Action buttons */}
			<div
				className={`flex items-center gap-2 border-t ${
					decided ? "border-border bg-card" : "border-foreground/15 bg-muted/20 dark:bg-muted/10"
				} px-4 py-3`}
			>
				{decided ? (
					<p className="flex items-center gap-1.5 text-sm text-muted-foreground">
						{decided === "approve" || decided === "edit" ? (
							<>
								<CheckIcon className="size-3.5 text-green-500" />
								{decided === "edit" ? "Approved with Changes" : "Approved"}
							</>
						) : (
							<>
								<XIcon className="size-3.5 text-destructive" />
								Rejected
							</>
						)}
					</p>
				) : isEditing ? (
					<>
						<Button
							size="sm"
							onClick={() => {
								setDecided("edit");
								setIsEditing(false);
								onDecision({
									type: "edit",
									edited_action: {
										name: interruptData.action_requests[0].name,
										args: buildFinalArgs(),
									},
								});
							}}
						>
							<CheckIcon />
							Approve with Changes
						</Button>
						<Button
							size="sm"
							variant="outline"
							onClick={() => {
								setIsEditing(false);
								setEditedArgs(initialEditState); // Reset to original args
							}}
						>
							Cancel
						</Button>
					</>
				) : (
					<>
						{allowedDecisions.includes("approve") && (
							<Button
								size="sm"
								onClick={() => {
									setDecided("approve");
									onDecision({
										type: "approve",
										edited_action: {
											name: interruptData.action_requests[0].name,
											args: buildFinalArgs(),
										},
									});
								}}
							>
								<CheckIcon />
								Approve
							</Button>
						)}
						{canEdit && (
							<Button size="sm" variant="outline" onClick={() => setIsEditing(true)}>
								<PencilIcon />
								Edit
							</Button>
						)}
						{allowedDecisions.includes("reject") && (
							<Button
								size="sm"
								variant="outline"
								onClick={() => {
									setDecided("reject");
									onDecision({ type: "reject", message: "User rejected the action." });
								}}
							>
								<XIcon />
								Reject
							</Button>
						)}
					</>
				)}
			</div>
		</div>
	);
}

function ErrorCard({ result }: { result: ErrorResult }) {
	return (
		<div className="my-4 max-w-md overflow-hidden rounded-xl border border-destructive/50 bg-card">
			<div className="flex items-center gap-3 border-b border-destructive/50 px-4 py-3">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-destructive/10">
					<XIcon className="size-4 text-destructive" />
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-sm font-medium text-destructive">Failed to update Linear issue</p>
				</div>
			</div>
			<div className="px-4 py-3">
				<p className="text-sm text-muted-foreground">{result.message}</p>
			</div>
		</div>
	);
}

function NotFoundCard({ result }: { result: NotFoundResult }) {
	return (
		<div className="my-4 max-w-md overflow-hidden rounded-xl border border-amber-500/50 bg-card">
			<div className="flex items-start gap-3 px-4 py-3">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-amber-500/10">
					<InfoIcon className="size-4 text-amber-500" />
				</div>
				<div className="min-w-0 flex-1 pt-2">
					<p className="text-sm text-muted-foreground">{result.message}</p>
				</div>
			</div>
		</div>
	);
}

function SuccessCard({ result }: { result: SuccessResult }) {
	return (
		<div className="my-4 max-w-md overflow-hidden rounded-xl border border-border bg-card">
			<div className="flex items-center gap-3 border-b border-border px-4 py-3">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-green-500/10">
					<CheckIcon className="size-4 text-green-500" />
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-[.8rem] text-muted-foreground">
						{result.message || "Linear issue updated successfully"}
					</p>
				</div>
			</div>
			<div className="space-y-2 px-4 py-3 text-xs">
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

export const UpdateLinearIssueToolUI = makeAssistantToolUI<
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
>({
	toolName: "update_linear_issue",
	render: function UpdateLinearIssueUI({ result, status }) {
		if (status.type === "running") {
			return (
				<div className="my-4 flex max-w-md items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
					<Loader2Icon className="size-4 animate-spin text-muted-foreground" />
					<p className="text-sm text-muted-foreground">Preparing Linear issue update...</p>
				</div>
			);
		}

		if (!result) return null;

		if (isInterruptResult(result)) {
			return (
				<ApprovalCard
					interruptData={result}
					onDecision={(decision) => {
						window.dispatchEvent(
							new CustomEvent("hitl-decision", { detail: { decisions: [decision] } })
						);
					}}
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
		if (isErrorResult(result)) return <ErrorCard result={result} />;

		return <SuccessCard result={result as SuccessResult} />;
	},
});
