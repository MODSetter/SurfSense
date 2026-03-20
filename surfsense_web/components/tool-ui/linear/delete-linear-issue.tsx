"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { CornerDownLeftIcon, TriangleAlertIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";

interface InterruptResult {
	__interrupt__: true;
	__decided__?: "approve" | "reject";
	action_requests: Array<{
		name: string;
		args: Record<string, unknown>;
	}>;
	review_configs: Array<{
		action_name: string;
		allowed_decisions: Array<"approve" | "reject">;
	}>;
	interrupt_type?: string;
	context?: {
		workspace?: { id: number; organization_name: string };
		issue?: {
			id: string;
			identifier: string;
			title: string;
			state?: string;
			document_id?: number;
			indexed_at?: string;
		};
		error?: string;
	};
}

interface SuccessResult {
	status: "success";
	deleted_from_kb?: boolean;
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

interface WarningResult {
	status: "success";
	warning: string;
	message?: string;
}

interface AuthErrorResult {
	status: "auth_error";
	message: string;
	connector_id?: number;
	connector_type: string;
}

type DeleteLinearIssueResult =
	| InterruptResult
	| SuccessResult
	| ErrorResult
	| NotFoundResult
	| WarningResult
	| AuthErrorResult;

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

function isWarningResult(result: unknown): result is WarningResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as WarningResult).status === "success" &&
		"warning" in result &&
		typeof (result as WarningResult).warning === "string"
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
	interruptData,
	onDecision,
}: {
	interruptData: InterruptResult;
	onDecision: (decision: {
		type: "approve" | "reject";
		message?: string;
		edited_action?: { name: string; args: Record<string, unknown> };
	}) => void;
}) {
	const actionArgs = interruptData.action_requests[0]?.args ?? {};
	const context = interruptData.context;
	const issue = context?.issue;

	const [decided, setDecided] = useState<"approve" | "reject" | null>(
		interruptData.__decided__ ?? null
	);
	const wasAlreadyDecided = interruptData.__decided__ != null;
	const [deleteFromKb, setDeleteFromKb] = useState(
		typeof actionArgs.delete_from_kb === "boolean" ? actionArgs.delete_from_kb : false
	);

	const handleApprove = useCallback(() => {
		if (decided) return;
		setDecided("approve");
		onDecision({
			type: "approve",
			edited_action: {
				name: interruptData.action_requests[0].name,
				args: {
					issue_id: issue?.id,
					connector_id: context?.workspace?.id,
					delete_from_kb: deleteFromKb,
				},
			},
		});
	}, [decided, onDecision, interruptData, issue?.id, context?.workspace?.id, deleteFromKb]);

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
						{decided === "reject"
							? "Linear Issue Deletion Rejected"
							: decided === "approve"
								? "Linear Issue Deletion Approved"
								: "Delete Linear Issue"}
					</p>
					{decided === "approve" ? (
						wasAlreadyDecided ? (
							<p className="text-xs text-muted-foreground mt-0.5">Issue deleted</p>
						) : (
							<TextShimmerLoader text="Deleting issue" size="sm" />
						)
					) : (
						<p className="text-xs text-muted-foreground mt-0.5">
							{decided === "reject"
								? "Issue deletion was cancelled"
								: "Requires your approval to proceed"}
						</p>
					)}
				</div>
			</div>

			{/* Context section — workspace + issue info (read-only) */}
			{!decided && (
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
										<p className="text-xs font-medium text-muted-foreground">Issue to Archive</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm space-y-1">
											<div className="font-medium">
												{issue.identifier}: {issue.title}
											</div>
											{issue.state && (
												<div className="text-xs text-muted-foreground">{issue.state}</div>
											)}
										</div>
									</div>
								)}
							</>
						)}
					</div>
				</>
			)}

			{/* delete_from_kb toggle */}
			{!decided && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 select-none">
					<div className="flex items-center gap-2.5">
						<Checkbox
							id="linear-delete-from-kb"
							checked={deleteFromKb}
							onCheckedChange={(v) => setDeleteFromKb(v === true)}
							className="shrink-0"
						/>
						<label htmlFor="linear-delete-from-kb" className="flex-1 cursor-pointer">
							<span className="text-sm text-foreground">Also remove from knowledge base</span>
							<p className="text-xs text-muted-foreground mt-0.5">
								This will permanently delete the issue from your knowledge base (cannot be undone)
							</p>
						</label>
					</div>
					</div>
				</>
			)}

			{/* Action buttons - only shown when pending */}
			{!decided && (
				<>
					<div className="mx-5 h-px bg-border/50" />
				<div className="px-5 py-4 flex items-center gap-2 select-none">
					<Button
						size="sm"
						className="rounded-lg gap-1.5"
						onClick={handleApprove}
						>
							Approve
							<CornerDownLeftIcon className="size-3 opacity-60" />
						</Button>
						<Button
							size="sm"
							variant="ghost"
							className="rounded-lg text-muted-foreground"
							onClick={() => {
								setDecided("reject");
								onDecision({ type: "reject", message: "User rejected the action." });
							}}
						>
							Reject
						</Button>
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
				<p className="text-sm font-semibold text-destructive">
					Linear authentication expired
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
				<p className="text-sm font-semibold text-destructive">Failed to delete Linear issue</p>
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
				<p className="text-sm font-semibold text-amber-600 dark:text-amber-400">
					Issue not found
				</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<p className="text-sm text-muted-foreground">{result.message}</p>
			</div>
		</div>
	);
}

function WarningCard({ result }: { result: WarningResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="flex items-start gap-3 border-b px-5 py-4">
				<TriangleAlertIcon className="size-4 mt-0.5 shrink-0 text-amber-500" />
				<p className="text-sm font-medium text-amber-600 dark:text-amber-500">Partial success</p>
			</div>
			<div className="px-5 py-4">
				<p className="text-sm text-muted-foreground">{result.warning}</p>
			</div>
		</div>
	);
}

function SuccessCard({ result }: { result: SuccessResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-foreground">
					{result.message || "Linear issue archived successfully"}
				</p>
			</div>
			{result.deleted_from_kb && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 text-xs">
						<span className="text-green-600 dark:text-green-500">
							Also removed from knowledge base
						</span>
					</div>
				</>
			)}
		</div>
	);
}

export const DeleteLinearIssueToolUI = makeAssistantToolUI<
	{ issue_ref: string; delete_from_kb?: boolean },
	DeleteLinearIssueResult
>({
	toolName: "delete_linear_issue",
	render: function DeleteLinearIssueUI({ result, status: _status }) {
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
		if (isAuthErrorResult(result)) return <AuthErrorCard result={result} />;
		if (isWarningResult(result)) return <WarningCard result={result} />;
		if (isErrorResult(result)) return <ErrorCard result={result} />;

		return <SuccessCard result={result as SuccessResult} />;
	},
});
