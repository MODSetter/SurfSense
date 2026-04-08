"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useSetAtom } from "jotai";
import { CornerDownLeftIcon, Pen } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { openHitlEditPanelAtom } from "@/atoms/chat/hitl-edit-panel.atom";
import { PlateEditor } from "@/components/editor/plate-editor";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { useHitlPhase } from "@/hooks/use-hitl-phase";

interface JiraAccount {
	id: number;
	name: string;
	base_url: string;
	auth_expired?: boolean;
}

interface JiraProject {
	id: string;
	key: string;
	name: string;
}

interface JiraIssueType {
	id: string;
	name: string;
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
		accounts?: JiraAccount[];
		projects?: JiraProject[];
		issue_types?: JiraIssueType[];
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

type CreateJiraIssueResult =
	| InterruptResult
	| SuccessResult
	| ErrorResult
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
		project_key: string;
		summary: string;
		issue_type?: string;
		description?: string;
		priority?: string;
	};
	interruptData: InterruptResult;
	onDecision: (decision: {
		type: "approve" | "reject" | "edit";
		message?: string;
		edited_action?: { name: string; args: Record<string, unknown> };
	}) => void;
}) {
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);
	const [isPanelOpen, setIsPanelOpen] = useState(false);
	const openHitlEditPanel = useSetAtom(openHitlEditPanelAtom);
	const [pendingEdits, setPendingEdits] = useState<{ title: string; description: string } | null>(
		null
	);

	const [selectedAccountId, setSelectedAccountId] = useState("");
	const [selectedProjectKey, setSelectedProjectKey] = useState(args.project_key ?? "");
	const [selectedIssueType, setSelectedIssueType] = useState(args.issue_type ?? "Task");
	const [selectedPriority, setSelectedPriority] = useState(args.priority ?? "__none__");

	const accounts = interruptData.context?.accounts ?? [];
	const projects = interruptData.context?.projects ?? [];
	const issueTypes = interruptData.context?.issue_types ?? [];
	const priorities = interruptData.context?.priorities ?? [];

	const validAccounts = useMemo(() => accounts.filter((a) => !a.auth_expired), [accounts]);
	const expiredAccounts = useMemo(() => accounts.filter((a) => a.auth_expired), [accounts]);

	const isSummaryValid = (pendingEdits?.title ?? args.summary ?? "").trim().length > 0;
	const canApprove = !!selectedAccountId && !!selectedProjectKey && isSummaryValid;

	const reviewConfig = interruptData.review_configs[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	const buildFinalArgs = useCallback(
		(overrides?: { title?: string; description?: string }) => {
			return {
				summary: overrides?.title ?? pendingEdits?.title ?? args.summary,
				description:
					overrides?.description ?? pendingEdits?.description ?? args.description ?? null,
				connector_id: selectedAccountId ? Number(selectedAccountId) : null,
				project_key: selectedProjectKey || null,
				issue_type: selectedIssueType === "__none__" ? null : selectedIssueType,
				priority: selectedPriority === "__none__" ? null : selectedPriority,
			};
		},
		[
			args.summary,
			args.description,
			selectedAccountId,
			selectedProjectKey,
			selectedIssueType,
			selectedPriority,
			pendingEdits,
		]
	);

	const handleApprove = useCallback(() => {
		if (phase !== "pending") return;
		if (isPanelOpen || !canApprove) return;
		if (!allowedDecisions.includes("approve")) return;
		const isEdited = pendingEdits !== null;
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
		canApprove,
		allowedDecisions,
		onDecision,
		interruptData,
		buildFinalArgs,
		pendingEdits,
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
							? "Jira Issue Rejected"
							: phase === "processing" || phase === "complete"
								? "Jira Issue Approved"
								: "Create Jira Issue"}
					</p>
					{phase === "processing" ? (
						<TextShimmerLoader
							text={pendingEdits ? "Creating issue with your changes" : "Creating issue"}
							size="sm"
						/>
					) : phase === "complete" ? (
						<p className="text-xs text-muted-foreground mt-0.5">
							{pendingEdits ? "Issue created with your changes" : "Issue created"}
						</p>
					) : phase === "rejected" ? (
						<p className="text-xs text-muted-foreground mt-0.5">Issue creation was cancelled</p>
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
								title: pendingEdits?.title ?? args.summary ?? "",
								content: pendingEdits?.description ?? args.description ?? "",
								toolName: "Jira Issue",
								onSave: (newTitle, newDescription) => {
									setIsPanelOpen(false);
									setPendingEdits({ title: newTitle, description: newDescription });
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

			{/* Context section — real pickers in pending */}
			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-3 space-y-3 select-none">
						{interruptData.context?.error ? (
							<p className="text-sm text-destructive">{interruptData.context.error}</p>
						) : (
							<>
								{accounts.length > 0 && (
									<div className="space-y-1.5">
										<p className="text-xs font-medium text-muted-foreground">
											Jira Account <span className="text-destructive">*</span>
										</p>
										<Select
											value={selectedAccountId}
											onValueChange={(v) => {
												setSelectedAccountId(v);
												setSelectedProjectKey("");
												setSelectedIssueType("Task");
												setSelectedPriority("__none__");
											}}
										>
											<SelectTrigger className="w-full">
												<SelectValue placeholder="Select an account" />
											</SelectTrigger>
											<SelectContent>
												{validAccounts.map((a) => (
													<SelectItem key={a.id} value={String(a.id)}>
														{a.name}
													</SelectItem>
												))}
												{expiredAccounts.map((a) => (
													<div
														key={a.id}
														className="relative flex w-full cursor-default items-center gap-2 rounded-sm py-1.5 px-2 text-sm select-none opacity-50 pointer-events-none"
													>
														{a.name} (expired, retry after re-auth)
													</div>
												))}
											</SelectContent>
										</Select>
									</div>
								)}

								{selectedAccountId && (
									<>
										<div className="space-y-1.5">
											<p className="text-xs font-medium text-muted-foreground">
												Project <span className="text-destructive">*</span>
											</p>
											<Select value={selectedProjectKey} onValueChange={setSelectedProjectKey}>
												<SelectTrigger className="w-full">
													<SelectValue placeholder="Select a project" />
												</SelectTrigger>
												<SelectContent>
													{projects.map((p) => (
														<SelectItem key={p.id} value={p.key}>
															{p.name} ({p.key})
														</SelectItem>
													))}
												</SelectContent>
											</Select>
										</div>

										<div className="grid grid-cols-2 gap-3">
											<div className="space-y-1.5">
												<p className="text-xs font-medium text-muted-foreground">Issue Type</p>
												<Select value={selectedIssueType} onValueChange={setSelectedIssueType}>
													<SelectTrigger className="w-full">
														<SelectValue placeholder="Task" />
													</SelectTrigger>
													<SelectContent>
														{issueTypes.length > 0 ? (
															issueTypes.map((t) => (
																<SelectItem key={t.id} value={t.name}>
																	{t.name}
																</SelectItem>
															))
														) : (
															<SelectItem value="Task">Task</SelectItem>
														)}
													</SelectContent>
												</Select>
											</div>
											<div className="space-y-1.5">
												<p className="text-xs font-medium text-muted-foreground">Priority</p>
												<Select value={selectedPriority} onValueChange={setSelectedPriority}>
													<SelectTrigger className="w-full">
														<SelectValue placeholder="Default" />
													</SelectTrigger>
													<SelectContent>
														<SelectItem value="__none__">Default</SelectItem>
														{priorities.map((p) => (
															<SelectItem key={p.id} value={p.name}>
																{p.name}
															</SelectItem>
														))}
													</SelectContent>
												</Select>
											</div>
										</div>
									</>
								)}
							</>
						)}
					</div>
				</>
			)}

			{/* Content preview */}
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 pt-3">
				{(pendingEdits?.title ?? args.summary) != null && (
					<p className="text-sm font-medium text-foreground">
						{pendingEdits?.title ?? args.summary}
					</p>
				)}
				{(pendingEdits?.description ?? args.description) != null && (
					<div
						className="max-h-[7rem] overflow-hidden text-sm"
						style={{
							maskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
							WebkitMaskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
						}}
					>
						<PlateEditor
							markdown={pendingEdits?.description ?? args.description ?? ""}
							readOnly
							preset="readonly"
							editorVariant="none"
							className="h-auto [&_[data-slate-editor]]:!min-h-0 [&_[data-slate-editor]>*:first-child]:!mt-0"
						/>
					</div>
				)}
			</div>

			{/* Action buttons */}
			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-3 flex items-center gap-2 select-none">
						{allowedDecisions.includes("approve") && (
							<Button
								size="sm"
								className="rounded-lg gap-1.5"
								onClick={handleApprove}
								disabled={!canApprove || isPanelOpen}
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
				<p className="text-sm font-semibold text-destructive">All Jira accounts expired</p>
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
				<p className="text-sm font-semibold text-destructive">Failed to create Jira issue</p>
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
					{result.message || "Jira issue created successfully"}
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

export const CreateJiraIssueToolUI = ({
	args,
	result,
}: ToolCallMessagePartProps<
	{
		project_key: string;
		summary: string;
		issue_type?: string;
		description?: string;
		priority?: string;
	},
	CreateJiraIssueResult
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

	if (isInsufficientPermissionsResult(result))
		return <InsufficientPermissionsCard result={result} />;
	if (isAuthErrorResult(result)) return <AuthErrorCard result={result} />;
	if (isErrorResult(result)) return <ErrorCard result={result} />;

	return <SuccessCard result={result as SuccessResult} />;
};
