"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { CalendarIcon, CornerDownLeftIcon, MailIcon, UserIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useHitlPhase } from "@/hooks/use-hitl-phase";

interface GmailAccount {
	id: number;
	name: string;
	email: string;
	auth_expired?: boolean;
}

interface GmailMessage {
	message_id: string;
	thread_id?: string;
	subject: string;
	sender: string;
	date: string;
	connector_id: number;
	document_id: number;
}

interface InterruptResult {
	__interrupt__: true;
	__decided__?: "approve" | "reject";
	__completed__?: boolean;
	action_requests: Array<{
		name: string;
		args: Record<string, unknown>;
	}>;
	review_configs: Array<{
		action_name: string;
		allowed_decisions: Array<"approve" | "reject">;
	}>;
	context?: {
		account?: GmailAccount;
		email?: GmailMessage;
		error?: string;
	};
}

interface SuccessResult {
	status: "success";
	message_id?: string;
	message?: string;
	deleted_from_kb?: boolean;
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
	connector_type?: string;
}

interface InsufficientPermissionsResult {
	status: "insufficient_permissions";
	connector_id: number;
	message: string;
}

type TrashGmailEmailResult =
	| InterruptResult
	| SuccessResult
	| ErrorResult
	| NotFoundResult
	| InsufficientPermissionsResult
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

function formatDate(dateStr: string): string {
	return new Date(dateStr).toLocaleDateString(undefined, { dateStyle: "medium" });
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
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);
	const [deleteFromKb, setDeleteFromKb] = useState(false);

	const context = interruptData.context;
	const account = context?.account;
	const email = context?.email;

	const handleApprove = useCallback(() => {
		if (phase !== "pending") return;
		setProcessing();
		onDecision({
			type: "approve",
			edited_action: {
				name: interruptData.action_requests[0].name,
				args: {
					message_id: email?.message_id,
					connector_id: email?.connector_id ?? account?.id,
					delete_from_kb: deleteFromKb,
				},
			},
		});
	}, [phase, setProcessing, onDecision, interruptData, email, account?.id, deleteFromKb]);

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
				<div className="flex items-center gap-2">
					<div>
						<p className="text-sm font-semibold text-foreground">
							{phase === "rejected"
								? "Email Trash Rejected"
								: phase === "processing" || phase === "complete"
									? "Email Trash Approved"
									: "Trash Email"}
						</p>
						{phase === "processing" ? (
							<TextShimmerLoader text="Trashing email" size="sm" />
						) : phase === "complete" ? (
							<p className="text-xs text-muted-foreground mt-0.5">Email trashed</p>
						) : phase === "rejected" ? (
							<p className="text-xs text-muted-foreground mt-0.5">Email trash was cancelled</p>
						) : (
							<p className="text-xs text-muted-foreground mt-0.5">
								Requires your approval to proceed
							</p>
						)}
					</div>
				</div>
			</div>

			{/* Context — read-only account and email info */}
			{phase !== "rejected" && context && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 space-y-4 select-none">
						{context.error ? (
							<p className="text-sm text-destructive">{context.error}</p>
						) : (
							<>
								{account && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">Gmail Account</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm">
											{account.name}
										</div>
									</div>
								)}

								{email && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">Email to Trash</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm space-y-1.5">
											<div className="flex items-center gap-1.5">
												<MailIcon className="size-3 shrink-0 text-muted-foreground" />
												<span className="font-medium">{email.subject}</span>
											</div>
											<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
												<UserIcon className="size-3 shrink-0" />
												<span>From: {email.sender}</span>
											</div>
											<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
												<CalendarIcon className="size-3 shrink-0" />
												<span>Date: {formatDate(email.date)}</span>
											</div>
										</div>
									</div>
								)}
							</>
						)}
					</div>
				</>
			)}

			{/* delete_from_kb toggle */}
			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 select-none">
						<div className="flex items-center gap-2.5">
							<Checkbox
								id="gmail-delete-from-kb"
								checked={deleteFromKb}
								onCheckedChange={(v) => setDeleteFromKb(v === true)}
								className="shrink-0"
							/>
							<label htmlFor="gmail-delete-from-kb" className="flex-1 cursor-pointer">
								<span className="text-sm text-foreground">Also remove from knowledge base</span>
								<p className="text-xs text-muted-foreground mt-0.5">
									This will permanently delete the email from your knowledge base (cannot be undone)
								</p>
							</label>
						</div>
					</div>
				</>
			)}

			{/* Action buttons */}
			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 flex items-center gap-2 select-none">
						<Button size="sm" className="rounded-lg gap-1.5" onClick={handleApprove}>
							Approve
							<CornerDownLeftIcon className="size-3 opacity-60" />
						</Button>
						<Button
							size="sm"
							variant="ghost"
							className="rounded-lg text-muted-foreground"
							onClick={() => {
								setRejected();
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

function ErrorCard({ result }: { result: ErrorResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">Failed to trash email</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<p className="text-sm text-muted-foreground">{result.message}</p>
			</div>
		</div>
	);
}

function AuthErrorCard({ result }: { result: AuthErrorResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">Gmail authentication expired</p>
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
					Additional Gmail permissions required
				</p>
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
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border border-amber-500/50 bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<div className="flex items-center gap-2">
					<p className="text-sm font-semibold text-amber-600 dark:text-amber-400">
						Email not found
					</p>
				</div>
			</div>
			<div className="mx-5 h-px bg-amber-500/30" />
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
					{result.message || "Email moved to trash successfully"}
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

export const TrashGmailEmailToolUI = ({
	result,
}: ToolCallMessagePartProps<
	{ email_subject_or_id: string; delete_from_kb?: boolean },
	TrashGmailEmailResult
>) => {
	if (!result) return null;

	if (isInterruptResult(result)) {
		return (
			<ApprovalCard
				interruptData={result}
				onDecision={(decision) => {
					const event = new CustomEvent("hitl-decision", {
						detail: { decisions: [decision] },
					});
					window.dispatchEvent(event);
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

	if (isAuthErrorResult(result)) return <AuthErrorCard result={result} />;
	if (isInsufficientPermissionsResult(result))
		return <InsufficientPermissionsCard result={result} />;
	if (isNotFoundResult(result)) return <NotFoundCard result={result} />;
	if (isErrorResult(result)) return <ErrorCard result={result} />;

	return <SuccessCard result={result as SuccessResult} />;
};
