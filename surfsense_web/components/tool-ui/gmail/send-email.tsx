"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useSetAtom } from "jotai";
import { CornerDownLeftIcon, MailIcon, Pen, UserIcon, UsersIcon } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ExtraField } from "@/atoms/chat/hitl-edit-panel.atom";
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
import { isInterruptResult, useHitlDecision } from "@/lib/hitl";
import type { HitlDecision, InterruptResult } from "@/lib/hitl";
import { useHitlPhase } from "@/hooks/use-hitl-phase";

interface GmailAccount {
	id: number;
	name: string;
	email: string;
	auth_expired?: boolean;
}

interface GmailSendEmailContext {
	accounts?: GmailAccount[];
	error?: string;
}

interface SuccessResult {
	status: "success";
	message_id?: string;
	message?: string;
}

interface ErrorResult {
	status: "error";
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

type SendGmailEmailResult =
	| InterruptResult<GmailSendEmailContext>
	| SuccessResult
	| ErrorResult
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
	args: { to: string; subject: string; body: string; cc?: string; bcc?: string };
	interruptData: InterruptResult<GmailSendEmailContext>;
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

	const accounts = interruptData.context?.accounts ?? [];
	const validAccounts = accounts.filter((a) => !a.auth_expired);
	const expiredAccounts = accounts.filter((a) => a.auth_expired);

	const defaultAccountId = useMemo(() => {
		if (validAccounts.length === 1) return String(validAccounts[0].id);
		return "";
	}, [validAccounts]);

	const [selectedAccountId, setSelectedAccountId] = useState<string>(defaultAccountId);

	const canApprove = !!selectedAccountId;

	const reviewConfig = interruptData.review_configs?.[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

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
				args: {
					...args,
					...(pendingEdits && {
						subject: pendingEdits.subject,
						body: pendingEdits.body,
						to: pendingEdits.to,
						cc: pendingEdits.cc,
						bcc: pendingEdits.bcc,
					}),
					connector_id: selectedAccountId ? Number(selectedAccountId) : null,
				},
			},
		});
	}, [
		phase,
		isPanelOpen,
		canApprove,
		allowedDecisions,
		setProcessing,
		onDecision,
		interruptData,
		args,
		selectedAccountId,
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
				<div className="flex items-center gap-2">
					<div>
						<p className="text-sm font-semibold text-foreground">
							{phase === "rejected"
								? "Email Sending Rejected"
								: phase === "processing" || phase === "complete"
									? "Email Sending Approved"
									: "Send Email"}
						</p>
						{phase === "processing" ? (
							<TextShimmerLoader
								text={pendingEdits ? "Sending email with your changes" : "Sending email"}
								size="sm"
							/>
						) : phase === "complete" ? (
							<p className="text-xs text-muted-foreground mt-0.5">
								{pendingEdits ? "Email sent with your changes" : "Email sent"}
							</p>
						) : phase === "rejected" ? (
							<p className="text-xs text-muted-foreground mt-0.5">Email sending was cancelled</p>
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
									value: pendingEdits?.to ?? args.to ?? "",
								},
								{
									key: "cc",
									label: "CC",
									type: "emails",
									value: pendingEdits?.cc ?? args.cc ?? "",
								},
								{
									key: "bcc",
									label: "BCC",
									type: "emails",
									value: pendingEdits?.bcc ?? args.bcc ?? "",
								},
							];
							openHitlEditPanel({
								title: pendingEdits?.subject ?? args.subject ?? "",
								content: pendingEdits?.body ?? args.body ?? "",
								toolName: "Send Email",
								extraFields,
								onSave: (newTitle, newContent, extraFieldValues) => {
									setIsPanelOpen(false);
									const extras = extraFieldValues ?? {};
									setPendingEdits({
										subject: newTitle,
										body: newContent,
										to: extras.to ?? pendingEdits?.to ?? args.to ?? "",
										cc: extras.cc ?? pendingEdits?.cc ?? args.cc ?? "",
										bcc: extras.bcc ?? pendingEdits?.bcc ?? args.bcc ?? "",
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

			{/* Account selector — real dropdown in pending */}
			{phase === "pending" && interruptData.context && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 space-y-4 select-none">
						{interruptData.context.error ? (
							<p className="text-sm text-destructive">{interruptData.context.error}</p>
						) : (
							accounts.length > 0 && (
								<div className="space-y-2">
									<p className="text-xs font-medium text-muted-foreground">
										Gmail Account <span className="text-destructive">*</span>
									</p>
									<Select value={selectedAccountId} onValueChange={setSelectedAccountId}>
										<SelectTrigger className="w-full">
											<SelectValue placeholder="Select an account" />
										</SelectTrigger>
										<SelectContent>
											{validAccounts.map((account) => (
												<SelectItem key={account.id} value={String(account.id)}>
													{account.name}
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
							)
						)}
					</div>
				</>
			)}

			{/* Email headers + body preview — visible in ALL phases */}
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 pt-3 pb-2 space-y-1.5 select-none">
				{(pendingEdits?.to ?? args.to) && (
					<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
						<UserIcon className="size-3 shrink-0" />
						<span>To: {pendingEdits?.to ?? args.to}</span>
					</div>
				)}
				{(pendingEdits?.cc ?? args.cc) && (pendingEdits?.cc ?? args.cc)?.trim() !== "" && (
					<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
						<UsersIcon className="size-3 shrink-0" />
						<span>CC: {pendingEdits?.cc ?? args.cc}</span>
					</div>
				)}
				{(pendingEdits?.bcc ?? args.bcc) && (pendingEdits?.bcc ?? args.bcc)?.trim() !== "" && (
					<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
						<UsersIcon className="size-3 shrink-0" />
						<span>BCC: {pendingEdits?.bcc ?? args.bcc}</span>
					</div>
				)}
			</div>

			<div className="px-5 pt-1">
				{(pendingEdits?.subject ?? args.subject) != null && (
					<p className="text-sm font-medium text-foreground">
						{pendingEdits?.subject ?? args.subject}
					</p>
				)}
				{(pendingEdits?.body ?? args.body) != null && (
					<div
						className="mt-2 max-h-[7rem] overflow-hidden text-sm"
						style={{
							maskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
							WebkitMaskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
						}}
					>
						<PlateEditor
							markdown={String(pendingEdits?.body ?? args.body)}
							readOnly
							preset="readonly"
							editorVariant="none"
							className="h-auto [&_[data-slate-editor]]:!min-h-0 [&_[data-slate-editor]>*:first-child]:!mt-0"
						/>
					</div>
				)}
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
								disabled={!canApprove || isPanelOpen}
							>
								Send
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

function ErrorCard({ result }: { result: ErrorResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">Failed to send email</p>
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

function SuccessCard({ result }: { result: SuccessResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<div className="flex items-center gap-2">
					<MailIcon className="size-4 text-muted-foreground shrink-0" />
					<p className="text-sm font-semibold text-foreground">
						{result.message || "Email sent successfully"}
					</p>
				</div>
			</div>
		</div>
	);
}

export const SendGmailEmailToolUI = ({
	args,
	result,
}: ToolCallMessagePartProps<
	{ to: string; subject: string; body: string; cc?: string; bcc?: string },
	SendGmailEmailResult
>) => {
	const { dispatch } = useHitlDecision();

	if (!result) return null;

	if (isInterruptResult(result)) {
		return (
			<ApprovalCard
				args={args}
				interruptData={result as InterruptResult<GmailSendEmailContext>}
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
	if (isErrorResult(result)) return <ErrorCard result={result} />;

	return <SuccessCard result={result as SuccessResult} />;
};
