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
import { useHitlPhase } from "@/hooks/use-hitl-phase";

interface JiraIssue {
	issue_id: string;
	issue_identifier: string;
	issue_title: string;
	state?: string;
	priority?: string;
	issue_type?: string;
	assignee?: string;
	description?: string;
	project?: string;
	document_id?: number;
}

interface JiraAccount {
	id: number;
	name: string;
	base_url: string;
	auth_expired?: boolean;
}

interface JiraPriority {
	id: string;
	name: string;
}

interface InterruptResult {
	__interrupt__: true;
	__decided__?: "approve" | "reject" | "edit";
	__completed__?: boolean;
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
		account?: JiraAccount;
		issue?: JiraIssue;
		priorities?: JiraPriority[];
		error?: string;
	};
}

interface SuccessResult {
	status: "success";
	issue_key: string;
	issue_url?: string;
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

interface InsufficientPermissionsResult {
	status: "insufficient_permissions";
	connector_id: number;
	message: string;
}

type UpdateJiraIssueResult =
	| InterruptResult
	| SuccessResult
	| ErrorResult
	| NotFoundResult
	| AuthErrorResult
	| InsufficientPermissionsResult;

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

function isAuthErrorResult(result: unknown): result is AuthErrorResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as AuthErrorResult).status === "auth_error"
	);
}

function isInsufficientPermissionsResult(result: unknown): result is InsufficientPermissionsResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as InsufficientPermissionsResult).status === "insufficient_permissions"
	);
}

function ApprovalCard({
	args,
	interruptData,
	onDecision,
}: {
	args: {
		issue_title_or_key: string;
		new_summary?: string;
		new_description?: string;
		new_priority?: string;
	};
	interruptData: InterruptResult;
	onDecision: (decision: {
		type: "approve" | "reject" | "edit";
		message?: string;
		edited_action?: { name: string; args: Record<string, unknown> };
	}) => void;
}) {
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);

	const actionArgs = interruptData.action_requests[0]?.args ?? {};
	const context = interruptData.context;
	const account = context?.account;
	const issue = context?.issue;
	const priorities = context?.priorities ?? [];

	const [isPanelOpen, setIsPanelOpen] = useState(false);
	const [editedArgs, setEditedArgs] = useState(() => ({
		summary: actionArgs.new_summary
			? String(actionArgs.new_summary)
			: (issue?.issue_title ?? args.new_summary ?? ""),
		description: actionArgs.new_description
			? String(actionArgs.new_description)
			: (issue?.description ?? args.new_description ?? ""),
		priority: actionArgs.new_priority
			? String(actionArgs.new_priority)
			: (issue?.priority ?? args.new_priority ?? "__none__"),
	}));
	const [hasPanelEdits, setHasPanelEdits] = useState(false);
	const openHitlEditPanel = useSetAtom(openHitlEditPanelAtom);

	const reviewConfig = interruptData.review_configs[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	const hasProposedChanges =
		actionArgs.new_summary ||
		args.new_summary ||
		actionArgs.new_description ||
		args.new_description ||
		actionArgs.new_priority ||
		args.new_priority;

	const buildFinalArgs = useCallback(() => {
		return {
			issue_id: issue?.issue_id,
			document_id: issue?.document_id,
			connector_id: account?.id,
			new_summary: editedArgs.summary || null,
			new_description: editedArgs.description || null,
			new_priority: editedArgs.priority === "__none__" ? null : editedArgs.priority,
		};
	}, [issue?.issue_id, issue?.document_id, account?.id, editedArgs]);

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
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 transition-all duration-300">
			{/* Header */}
			<div className="flex items-start justify-between px-5 pt-5 pb-4 select-none">
				<div>
					<p className="text-sm font-semibold text-foreground">
						{phase === "rejected"
							? "Jira Issue Update Rejected"
							: phase === "processing" || phase === "complete"
								? "Jira Issue Update Approved"
								: "Update Jira Issue"}
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
								title: editedArgs.summary,
								content: editedArgs.description,
								toolName: "Jira Issue",
								onSave: (newTitle, newDescription) => {
									setIsPanelOpen(false);
									setEditedArgs((prev) => ({
										...prev,
										summary: newTitle,
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

			{/* Context section — account + current issue + pickers in pending */}
			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 space-y-4 select-none">
						{context?.error ? (
							<p className="text-sm text-destructive">{context.error}</p>
						) : (
							<>
								{account && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">Jira Account</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm">
											{account.name}
										</div>
									</div>
								)}

								{issue && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">Current Issue</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm space-y-1.5">
											<div className="font-medium">
												{issue.issue_identifier}: {issue.issue_title}
											</div>
											<div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
												{issue.state && (
													<Badge className="rounded-full border-0 bg-muted text-muted-foreground">
														{issue.state}
													</Badge>
												)}
												{issue.issue_type && <span>{issue.issue_type}</span>}
												{issue.assignee && <span>{issue.assignee}</span>}
												{issue.priority && <span>Priority: {issue.priority}</span>}
											</div>
											{issue.project && (
												<div className="text-xs text-muted-foreground">
													Project: {issue.project}
												</div>
											)}
										</div>
									</div>
								)}

								{priorities.length > 0 && (
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
												<SelectItem value="__none__">No change</SelectItem>
												{priorities.map((p) => (
													<SelectItem key={p.id} value={p.name}>
														{p.name}
													</SelectItem>
												))}
											</SelectContent>
										</Select>
									</div>
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
						{(hasPanelEdits
							? editedArgs.summary
							: (actionArgs.new_summary ?? args.new_summary)) && (
							<p className="text-sm font-medium text-foreground">
								{String(
									hasPanelEdits ? editedArgs.summary : (actionArgs.new_summary ?? args.new_summary)
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
						{(actionArgs.new_priority ?? args.new_priority) && (
							<div className="mt-2">
								<span className="text-xs text-muted-foreground">Priority → </span>
								<span className="text-xs font-medium">
									{String(actionArgs.new_priority ?? args.new_priority)}
								</span>
							</div>
						)}
					</>
				) : (
					<p className="text-sm text-muted-foreground italic pb-3">No changes proposed</p>
				)}
			</div>

			{/* Action buttons */}
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
				<p className="text-sm font-semibold text-destructive">Jira authentication expired</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<p className="text-sm text-muted-foreground">{result.message}</p>
			</div>
		</div>
	);
}

function InsufficientPermissionsCard({ result }: { result: InsufficientPermissionsResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">
					Additional Jira permissions required
				</p>
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
				<p className="text-sm font-semibold text-destructive">Failed to update Jira issue</p>
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
					{result.message || "Jira issue updated successfully"}
				</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4 space-y-2 text-xs">
				{result.issue_url ? (
					<a
						href={result.issue_url}
						target="_blank"
						rel="noopener noreferrer"
						className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
					>
						Open in Jira
					</a>
				) : (
					<div>
						<span className="font-medium text-muted-foreground">Issue Key: </span>
						<span>{result.issue_key}</span>
					</div>
				)}
			</div>
		</div>
	);
}

export const UpdateJiraIssueToolUI = ({
	args,
	result,
}: ToolCallMessagePartProps<
	{
		issue_title_or_key: string;
		new_summary?: string;
		new_description?: string;
		new_priority?: string;
	},
	UpdateJiraIssueResult
>) => {
	if (!result) return null;

	if (isInterruptResult(result)) {
		return (
			<ApprovalCard
				args={args}
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
	if (isInsufficientPermissionsResult(result))
		return <InsufficientPermissionsCard result={result} />;
	if (isAuthErrorResult(result)) return <AuthErrorCard result={result} />;
	if (isErrorResult(result)) return <ErrorCard result={result} />;

	return <SuccessCard result={result as SuccessResult} />;
};
