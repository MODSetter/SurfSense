"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useSetAtom } from "jotai";
import { CornerDownLeftIcon, MailIcon, Pen, UserIcon, UsersIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import type { ExtraField } from "@/atoms/chat/hitl-edit-panel.atom";
import { openHitlEditPanelAtom } from "@/atoms/chat/hitl-edit-panel.atom";
import { PlateEditor } from "@/components/editor/plate-editor";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import { useHitlPhase } from "@/hooks/use-hitl-phase";
import type { HitlDecision, InterruptResult } from "@/lib/hitl";
import { isInterruptResult, useHitlDecision } from "@/lib/hitl";

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

type GmailUpdateDraftContext = {
	account?: GmailAccount;
	email?: GmailMessage;
	draft_id?: string;
	existing_body?: string;
	error?: string;
};

interface SuccessResult {
	status: "success";
	draft_id?: string;
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
	connector_type?: string;
}

interface InsufficientPermissionsResult {
	status: "insufficient_permissions";
	connector_id: number;
	message: string;
}

type UpdateGmailDraftResult =
	| InterruptResult<GmailUpdateDraftContext>
	| SuccessResult
	| ErrorResult
	| NotFoundResult
	| InsufficientPermissionsResult
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
		draft_subject_or_id: string;
		body: string;
		to?: string;
		subject?: string;
		cc?: string;
		bcc?: string;
	};
	interruptData: InterruptResult<GmailUpdateDraftContext>;
	onDecision: (decision: HitlDecision) => void;
}) {
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);
	const [isPanelOpen, setIsPanelOpen] = useState(false);
	const openHitlEditPanel = useSetAtom(openHitlEditPanelAtom);
	const [pendingEdits, setPendingEdits] = useState<{
		subject: string;
		body: string;
		to: string;
		cc: string;
		bcc: string;
	} | null>(null);

	const context = interruptData.context;
	const account = context?.account;
	const email = context?.email;
	const draftId = context?.draft_id;
	const existingBody = context?.existing_body;

	const reviewConfig = interruptData.review_configs?.[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	const currentSubject =
		pendingEdits?.subject ?? args.subject ?? email?.subject ?? args.draft_subject_or_id;
	const currentBody = pendingEdits?.body ?? args.body;
	const currentTo = pendingEdits?.to ?? args.to ?? "";
	const currentCc = pendingEdits?.cc ?? args.cc ?? "";
	const currentBcc = pendingEdits?.bcc ?? args.bcc ?? "";
	const editableBody = currentBody || existingBody || "";

	const handleApprove = useCallback(() => {
		if (phase !== "pending") return;
		if (isPanelOpen) return;
		if (!allowedDecisions.includes("approve")) return;
		const isEdited = pendingEdits !== null;
		setProcessing();
		onDecision({
			type: isEdited ? "edit" : "approve",
			edited_action: {
				name: interruptData.action_requests[0].name,
				args: {
					message_id: email?.message_id,
					draft_id: draftId,
					to: currentTo,
					subject: currentSubject,
					body: editableBody,
					cc: currentCc,
					bcc: currentBcc,
					connector_id: email?.connector_id ?? account?.id,
				},
			},
		});
	}, [
		phase,
		isPanelOpen,
		allowedDecisions,
		setProcessing,
		onDecision,
		interruptData,
		email,
		account?.id,
		draftId,
		pendingEdits,
		currentSubject,
		editableBody,
		currentTo,
		currentCc,
		currentBcc,
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
				<div className="flex items-center gap-2">
					<div>
						<p className="text-sm font-semibold text-foreground">
							{phase === "rejected"
								? "Draft Update Rejected"
								: phase === "processing" || phase === "complete"
									? "Draft Update Approved"
									: "Update Gmail Draft"}
						</p>
						{phase === "processing" ? (
							<TextShimmerLoader
								text={pendingEdits ? "Updating draft with your changes" : "Updating draft"}
								size="sm"
							/>
						) : phase === "complete" ? (
							<p className="text-xs text-muted-foreground mt-0.5">
								{pendingEdits ? "Draft updated with your changes" : "Draft updated"}
							</p>
						) : phase === "rejected" ? (
							<p className="text-xs text-muted-foreground mt-0.5">Draft update was cancelled</p>
						) : (
							<p className="text-xs text-muted-foreground mt-0.5">
								Requires your approval to proceed
							</p>
						)}
					</div>
				</div>
				{phase === "pending" && canEdit && (
					<Button
						size="sm"
						variant="ghost"
						className="rounded-lg text-muted-foreground -mt-1 -mr-2"
						onClick={() => {
							setIsPanelOpen(true);
							const extraFields: ExtraField[] = [
								{
									key: "to",
									label: "To",
									type: "emails",
									value: currentTo,
								},
								{
									key: "cc",
									label: "CC",
									type: "emails",
									value: currentCc,
								},
								{
									key: "bcc",
									label: "BCC",
									type: "emails",
									value: currentBcc,
								},
							];
							openHitlEditPanel({
								title: currentSubject,
								content: editableBody,
								toolName: "Gmail Draft",
								extraFields,
								onSave: (newTitle, newContent, extraFieldValues) => {
									setIsPanelOpen(false);
									const extras = extraFieldValues ?? {};
									setPendingEdits({
										subject: newTitle,
										body: newContent,
										to: extras.to ?? currentTo,
										cc: extras.cc ?? currentCc,
										bcc: extras.bcc ?? currentBcc,
									});
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

			{/* Context — account and draft info in pending/processing/complete */}
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
										<p className="text-xs font-medium text-muted-foreground">Draft to Update</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm space-y-1">
											<div className="flex items-center gap-1.5">
												<MailIcon className="size-3 shrink-0 text-muted-foreground" />
												<span className="font-medium">{email.subject}</span>
											</div>
										</div>
									</div>
								)}
							</>
						)}
					</div>
				</>
			)}

			{/* Email headers + body preview — visible in ALL phases */}
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 pt-3 pb-2 space-y-1.5 select-none">
				{currentTo && (
					<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
						<UserIcon className="size-3 shrink-0" />
						<span>To: {currentTo}</span>
					</div>
				)}
				{currentCc && currentCc.trim() !== "" && (
					<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
						<UsersIcon className="size-3 shrink-0" />
						<span>CC: {currentCc}</span>
					</div>
				)}
				{currentBcc && currentBcc.trim() !== "" && (
					<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
						<UsersIcon className="size-3 shrink-0" />
						<span>BCC: {currentBcc}</span>
					</div>
				)}
			</div>

			<div className="px-5 pt-1">
				{currentSubject != null && (
					<p className="text-sm font-medium text-foreground">{currentSubject}</p>
				)}
				{editableBody ? (
					<div
						className="mt-2 max-h-[7rem] overflow-hidden text-sm"
						style={{
							maskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
							WebkitMaskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
						}}
					>
						<PlateEditor
							markdown={String(editableBody)}
							readOnly
							preset="readonly"
							editorVariant="none"
							className="h-auto [&_[data-slate-editor]]:!min-h-0 [&_[data-slate-editor]>*:first-child]:!mt-0"
						/>
					</div>
				) : null}
			</div>

			{/* Action buttons — only in pending */}
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
									onDecision({
										type: "reject",
										message: "User rejected the action.",
									});
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

function ErrorCard({ result }: { result: ErrorResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">Failed to update Gmail draft</p>
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
						Draft not found
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
					{result.message || "Gmail draft updated successfully"}
				</p>
			</div>
		</div>
	);
}

export const UpdateGmailDraftToolUI = ({
	args,
	result,
}: ToolCallMessagePartProps<
	{
		draft_subject_or_id: string;
		body: string;
		to?: string;
		subject?: string;
		cc?: string;
		bcc?: string;
	},
	UpdateGmailDraftResult
>) => {
	const { dispatch } = useHitlDecision();

	if (!result) return null;

	if (isInterruptResult(result)) {
		return (
			<ApprovalCard
				args={args}
				interruptData={result as InterruptResult<GmailUpdateDraftContext>}
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

	if (isAuthErrorResult(result)) return <AuthErrorCard result={result} />;
	if (isInsufficientPermissionsResult(result))
		return <InsufficientPermissionsCard result={result} />;
	if (isNotFoundResult(result)) return <NotFoundCard result={result} />;
	if (isErrorResult(result)) return <ErrorCard result={result} />;

	return <SuccessCard result={result as SuccessResult} />;
};
