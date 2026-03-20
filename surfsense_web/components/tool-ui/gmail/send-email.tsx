"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
	CornerDownLeftIcon,
	MailIcon,
	Pen,
	SendIcon,
	UserIcon,
	UsersIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { PlateEditor } from "@/components/editor/plate-editor";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { useSetAtom } from "jotai";
import { openHitlEditPanelAtom } from "@/atoms/chat/hitl-edit-panel.atom";
import type { ExtraField } from "@/atoms/chat/hitl-edit-panel.atom";

interface GmailAccount {
	id: number;
	name: string;
	email: string;
	auth_expired?: boolean;
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
	context?: {
		accounts?: GmailAccount[];
		error?: string;
	};
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
	| InterruptResult
	| SuccessResult
	| ErrorResult
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
	interruptData: InterruptResult;
	onDecision: (decision: {
		type: "approve" | "reject" | "edit";
		message?: string;
		edited_action?: { name: string; args: Record<string, unknown> };
	}) => void;
}) {
	const [decided, setDecided] = useState<"approve" | "reject" | "edit" | null>(
		interruptData.__decided__ ?? null
	);
	const wasAlreadyDecided = interruptData.__decided__ != null;
	const [isPanelOpen, setIsPanelOpen] = useState(false);
	const openHitlEditPanel = useSetAtom(openHitlEditPanelAtom);

	const accounts = interruptData.context?.accounts ?? [];
	const validAccounts = accounts.filter((a) => !a.auth_expired);
	const expiredAccounts = accounts.filter((a) => a.auth_expired);

	const defaultAccountId = useMemo(() => {
		if (validAccounts.length === 1) return String(validAccounts[0].id);
		return "";
	}, [validAccounts]);

	const [selectedAccountId, setSelectedAccountId] = useState<string>(defaultAccountId);

	const canApprove = !!selectedAccountId;

	const reviewConfig = interruptData.review_configs[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	const handleApprove = useCallback(() => {
		if (decided || isPanelOpen || !canApprove) return;
		if (!allowedDecisions.includes("approve")) return;
		setDecided("approve");
		onDecision({
			type: "approve",
			edited_action: {
				name: interruptData.action_requests[0].name,
				args: {
					...args,
					connector_id: selectedAccountId ? Number(selectedAccountId) : null,
				},
			},
		});
	}, [decided, isPanelOpen, canApprove, allowedDecisions, onDecision, interruptData, args, selectedAccountId]);

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
				<div className="flex items-center gap-2">
					<SendIcon className="size-4 text-muted-foreground shrink-0" />
					<div>
						<p className="text-sm font-semibold text-foreground">
							{decided === "reject"
								? "Email Sending Rejected"
								: decided === "approve" || decided === "edit"
									? "Email Sending Approved"
									: "Send Email"}
						</p>
						{decided === "approve" || decided === "edit" ? (
							wasAlreadyDecided ? (
								<p className="text-xs text-muted-foreground mt-0.5">
									{decided === "edit" ? "Email sent with your changes" : "Email sent"}
								</p>
							) : (
								<TextShimmerLoader text={decided === "edit" ? "Sending email with your changes" : "Sending email"} size="sm" />
							)
						) : (
							<p className="text-xs text-muted-foreground mt-0.5">
								{decided === "reject"
									? "Email sending was cancelled"
									: "Requires your approval to proceed"}
							</p>
						)}
					</div>
				</div>
				{!decided && canEdit && (
					<Button
						size="sm"
						variant="ghost"
						className="rounded-lg text-muted-foreground -mt-1 -mr-2"
						onClick={() => {
							setIsPanelOpen(true);
							const extraFields: ExtraField[] = [
								{ key: "to", label: "To", type: "email", value: args.to || "" },
								{ key: "cc", label: "CC", type: "email", value: args.cc || "" },
								{ key: "bcc", label: "BCC", type: "email", value: args.bcc || "" },
							];
							openHitlEditPanel({
								title: args.subject ?? "",
								content: args.body ?? "",
								toolName: "Send Email",
								extraFields,
								onSave: (newTitle, newContent, extraFieldValues) => {
									setIsPanelOpen(false);
									setDecided("edit");
									const extras = extraFieldValues ?? {};
									onDecision({
										type: "edit",
										edited_action: {
											name: interruptData.action_requests[0].name,
											args: {
												...args,
												subject: newTitle,
												body: newContent,
												to: extras.to ?? args.to,
												cc: extras.cc ?? args.cc,
												bcc: extras.bcc ?? args.bcc,
												connector_id: selectedAccountId ? Number(selectedAccountId) : null,
											},
										},
									});
								},
							});
						}}
					>
						<Pen className="size-3.5" />
						Edit
					</Button>
				)}
			</div>

			{/* Account selector */}
			{!decided && interruptData.context && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 space-y-4 select-none">
						{interruptData.context.error ? (
							<p className="text-sm text-destructive">{interruptData.context.error}</p>
						) : (
							<>
								{accounts.length > 0 && (
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
														{account.email}
													</SelectItem>
												))}
												{expiredAccounts.map((a) => (
													<div
														key={a.id}
														className="relative flex w-full cursor-default items-center gap-2 rounded-sm py-1.5 px-2 text-sm select-none opacity-50 pointer-events-none"
													>
														{a.email} (expired, retry after re-auth)
													</div>
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

			{/* Email headers + body preview */}
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 pt-3 pb-2 space-y-1.5 select-none">
				{args.to && (
					<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
						<UserIcon className="size-3 shrink-0" />
						<span>To: {args.to}</span>
					</div>
				)}
				{args.cc && args.cc.trim() !== "" && (
					<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
						<UsersIcon className="size-3 shrink-0" />
						<span>CC: {args.cc}</span>
					</div>
				)}
				{args.bcc && args.bcc.trim() !== "" && (
					<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
						<UsersIcon className="size-3 shrink-0" />
						<span>BCC: {args.bcc}</span>
					</div>
				)}
			</div>

			<div className="px-5 pt-1">
				{args.subject != null && (
					<p className="text-sm font-medium text-foreground">{args.subject}</p>
				)}
				{args.body != null && (
					<div
						className="mt-2 max-h-[7rem] overflow-hidden text-sm"
						style={{
							maskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
							WebkitMaskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
						}}
					>
						<PlateEditor
							markdown={String(args.body)}
							readOnly
							preset="readonly"
							editorVariant="none"
							className="h-auto [&_[data-slate-editor]]:!min-h-0 [&_[data-slate-editor]>*:first-child]:!mt-0"
						/>
					</div>
				)}
			</div>

			{/* Action buttons */}
			{!decided && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 flex items-center gap-2 select-none">
						{allowedDecisions.includes("approve") && (
							<Button
								size="sm"
								className="rounded-lg gap-1.5"
								onClick={handleApprove}
								disabled={!canApprove}
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
								onClick={() => {
									setDecided("reject");
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
				<p className="text-sm font-semibold text-destructive">
					Gmail authentication expired
				</p>
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

export const SendGmailEmailToolUI = makeAssistantToolUI<
	{ to: string; subject: string; body: string; cc?: string; bcc?: string },
	SendGmailEmailResult
>({
	toolName: "send_gmail_email",
	render: function SendGmailEmailUI({ args, result, status: _status }) {
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

		if (isAuthErrorResult(result)) return <AuthErrorCard result={result} />;
		if (isInsufficientPermissionsResult(result))
			return <InsufficientPermissionsCard result={result} />;
		if (isErrorResult(result)) return <ErrorCard result={result} />;

		return <SuccessCard result={result as SuccessResult} />;
	},
});
