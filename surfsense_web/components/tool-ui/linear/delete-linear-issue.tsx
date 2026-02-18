"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
	AlertTriangleIcon,
	CheckIcon,
	InfoIcon,
	Loader2Icon,
	TriangleAlertIcon,
	XIcon,
} from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";

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
			url?: string;
			current_state?: string;
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

type DeleteLinearIssueResult =
	| InterruptResult
	| SuccessResult
	| ErrorResult
	| NotFoundResult
	| WarningResult;

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
	const [deleteFromKb, setDeleteFromKb] = useState(
		typeof actionArgs.delete_from_kb === "boolean" ? actionArgs.delete_from_kb : false
	);

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
					<p className="text-sm font-medium text-foreground">Delete Linear Issue</p>
					<p className="truncate text-xs text-muted-foreground">
						Requires your approval to proceed
					</p>
				</div>
			</div>

			{/* Context section — workspace + issue info (read-only) */}
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
									<div className="text-xs font-medium text-muted-foreground">Issue to Archive</div>
									<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm space-y-1">
										<div className="font-medium">
											{issue.identifier}: {issue.title}
										</div>
										{issue.current_state && (
											<div className="text-xs text-muted-foreground">{issue.current_state}</div>
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

			{/* delete_from_kb toggle */}
			{!decided && (
				<div className="px-4 py-3 border-b border-border bg-muted/20">
					<label className="flex items-start gap-2 cursor-pointer">
						<input
							type="checkbox"
							checked={deleteFromKb}
							onChange={(e) => setDeleteFromKb(e.target.checked)}
							className="mt-0.5"
						/>
						<div className="flex-1">
							<span className="text-sm text-foreground">Also remove from knowledge base</span>
							<p className="text-xs text-muted-foreground mt-1">
								⚠️ This will permanently delete the issue from your knowledge base (cannot be undone)
							</p>
						</div>
					</label>
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
						{decided === "approve" ? (
							<>
								<CheckIcon className="size-3.5 text-green-500" />
								Approved
							</>
						) : (
							<>
								<XIcon className="size-3.5 text-destructive" />
								Rejected
							</>
						)}
					</p>
				) : (
					<>
						<Button
							size="sm"
							onClick={() => {
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
							}}
						>
							<CheckIcon />
							Approve
						</Button>
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
					<p className="text-sm font-medium text-destructive">Failed to delete Linear issue</p>
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

function WarningCard({ result }: { result: WarningResult }) {
	return (
		<div className="my-4 max-w-md overflow-hidden rounded-xl border border-amber-500/50 bg-card">
			<div className="flex items-center gap-3 border-b border-amber-500/50 px-4 py-3">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-amber-500/10">
					<TriangleAlertIcon className="size-4 text-amber-500" />
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-sm font-medium text-amber-600 dark:text-amber-500">Partial success</p>
				</div>
			</div>
			<div className="px-4 py-3">
				<p className="text-sm text-muted-foreground">{result.warning}</p>
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
						{result.message || "Linear issue archived successfully"}
					</p>
				</div>
			</div>
			{result.deleted_from_kb && (
				<div className="px-4 py-3 text-xs">
					<span className="text-green-600 dark:text-green-500">
						✓ Also removed from knowledge base
					</span>
				</div>
			)}
		</div>
	);
}

export const DeleteLinearIssueToolUI = makeAssistantToolUI<
	{ issue_ref: string; delete_from_kb?: boolean },
	DeleteLinearIssueResult
>({
	toolName: "delete_linear_issue",
	render: function DeleteLinearIssueUI({ result, status }) {
		if (status.type === "running") {
			return (
				<div className="my-4 flex max-w-md items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
					<Loader2Icon className="size-4 animate-spin text-muted-foreground" />
					<p className="text-sm text-muted-foreground">Preparing Linear issue deletion...</p>
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
		if (isWarningResult(result)) return <WarningCard result={result} />;
		if (isErrorResult(result)) return <ErrorCard result={result} />;

		return <SuccessCard result={result as SuccessResult} />;
	},
});
