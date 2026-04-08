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

interface InterruptResult {
	__interrupt__: true;
	__decided__?: "approve" | "reject" | "edit";
	__completed__?: boolean;
	action_requests: Array<{
		name: string;
		args: Record<string, unknown>;
		description?: string;
	}>;
	review_configs: Array<{
		action_name: string;
		allowed_decisions: Array<"approve" | "edit" | "reject">;
	}>;
	interrupt_type?: string;
	message?: string;
	context?: {
		accounts?: Array<{
			id: number;
			name: string;
			workspace_id: string | null;
			workspace_name: string;
			workspace_icon: string;
			auth_expired?: boolean;
		}>;
		parent_pages?: Record<
			number,
			Array<{
				page_id: string;
				title: string;
				document_id: number;
			}>
		>;
		error?: string;
	};
}

interface SuccessResult {
	status: "success";
	page_id: string;
	title: string;
	url: string;
	content_preview?: string;
	content_length?: number;
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

type CreateNotionPageResult = InterruptResult | SuccessResult | ErrorResult | AuthErrorResult;

function isInterruptResult(result: unknown): result is InterruptResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"__interrupt__" in result &&
		(result as InterruptResult).__interrupt__ === true
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

function isErrorResult(result: unknown): result is ErrorResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as ErrorResult).status === "error"
	);
}

function ApprovalCard({
	args,
	interruptData,
	onDecision,
}: {
	args: Record<string, unknown>;
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
	const [pendingEdits, setPendingEdits] = useState<{ title: string; content: string } | null>(null);

	const accounts = interruptData.context?.accounts ?? [];
	const validAccounts = accounts.filter((a) => !a.auth_expired);
	const expiredAccounts = accounts.filter((a) => a.auth_expired);
	const parentPages = interruptData.context?.parent_pages ?? {};

	const defaultAccountId = useMemo(() => {
		if (args.connector_id) return String(args.connector_id);
		if (validAccounts.length === 1) return String(validAccounts[0].id);
		return "";
	}, [args.connector_id, validAccounts]);

	const [selectedAccountId, setSelectedAccountId] = useState<string>(defaultAccountId);
	const [selectedParentPageId, setSelectedParentPageId] = useState<string>(
		args.parent_page_id ? String(args.parent_page_id) : "__none__"
	);

	const availableParentPages = useMemo(() => {
		if (!selectedAccountId) return [];
		return parentPages[Number(selectedAccountId)] ?? [];
	}, [selectedAccountId, parentPages]);

	const isTitleValid = useMemo(() => {
		const title = pendingEdits?.title ?? args.title;
		return title && typeof title === "string" && title.trim().length > 0;
	}, [pendingEdits?.title, args.title]);

	const reviewConfig = interruptData.review_configs[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	const handleApprove = useCallback(() => {
		if (phase !== "pending") return;
		if (isPanelOpen || !selectedAccountId || !isTitleValid) return;
		if (!allowedDecisions.includes("approve")) return;
		const isEdited = pendingEdits !== null;
		setProcessing();
		onDecision({
			type: isEdited ? "edit" : "approve",
			edited_action: {
				name: interruptData.action_requests[0].name,
				args: {
					...args,
					...(pendingEdits && { title: pendingEdits.title, content: pendingEdits.content }),
					connector_id: selectedAccountId ? Number(selectedAccountId) : null,
					parent_page_id: selectedParentPageId === "__none__" ? null : selectedParentPageId,
				},
			},
		});
	}, [
		phase,
		isPanelOpen,
		selectedAccountId,
		isTitleValid,
		allowedDecisions,
		setProcessing,
		onDecision,
		interruptData,
		args,
		selectedParentPageId,
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
							? "Notion Page Rejected"
							: phase === "processing" || phase === "complete"
								? "Notion Page Approved"
								: "Create Notion Page"}
					</p>
					{phase === "processing" ? (
						<TextShimmerLoader
							text={pendingEdits ? "Creating page with your changes" : "Creating page"}
							size="sm"
						/>
					) : phase === "complete" ? (
						<p className="text-xs text-muted-foreground mt-0.5">
							{pendingEdits ? "Page created with your changes" : "Page created"}
						</p>
					) : phase === "rejected" ? (
						<p className="text-xs text-muted-foreground mt-0.5">Page creation was cancelled</p>
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
								title: pendingEdits?.title ?? String(args.title ?? ""),
								content: pendingEdits?.content ?? String(args.content ?? ""),
								toolName: "Notion Page",
								onSave: (newTitle, newContent) => {
									setIsPanelOpen(false);
									setPendingEdits({ title: newTitle, content: newContent });
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

			{/* Account/workspace picker — real UI in pending */}
			{phase === "pending" && interruptData.context && (
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
											Notion Account <span className="text-destructive">*</span>
										</p>
										<Select
											value={selectedAccountId}
											onValueChange={(value) => {
												setSelectedAccountId(value);
												setSelectedParentPageId("__none__");
											}}
										>
											<SelectTrigger className="w-full">
												<SelectValue placeholder="Select an account" />
											</SelectTrigger>
											<SelectContent>
												{validAccounts.map((account) => (
													<SelectItem key={account.id} value={String(account.id)}>
														{account.workspace_name}
													</SelectItem>
												))}
												{expiredAccounts.map((a) => (
													<div
														key={a.id}
														className="relative flex w-full cursor-default items-center gap-2 rounded-sm py-1.5 px-2 text-sm select-none opacity-50 pointer-events-none"
													>
														{a.workspace_name} (expired, retry after re-auth)
													</div>
												))}
											</SelectContent>
										</Select>
									</div>
								)}

								{selectedAccountId && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">
											Parent Page (optional)
										</p>
										<Select value={selectedParentPageId} onValueChange={setSelectedParentPageId}>
											<SelectTrigger className="w-full">
												<SelectValue placeholder="None" />
											</SelectTrigger>
											<SelectContent>
												<SelectItem value="__none__">None</SelectItem>
												{availableParentPages.map((page) => (
													<SelectItem key={page.page_id} value={page.page_id}>
														{page.title}
													</SelectItem>
												))}
											</SelectContent>
										</Select>
										{availableParentPages.length === 0 && selectedAccountId && (
											<p className="text-xs text-muted-foreground">
												No pages available. Page will be created at workspace root.
											</p>
										)}
									</div>
								)}
							</>
						)}
					</div>
				</>
			)}

			{/* Content preview */}
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 pt-3">
				{(pendingEdits?.title ?? args.title) != null && (
					<p className="text-sm font-medium text-foreground">
						{String(pendingEdits?.title ?? args.title)}
					</p>
				)}
				{(pendingEdits?.content ?? args.content) != null && (
					<div
						className="max-h-[7rem] overflow-hidden text-sm"
						style={{
							maskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
							WebkitMaskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
						}}
					>
						<PlateEditor
							markdown={String(pendingEdits?.content ?? args.content)}
							readOnly
							preset="readonly"
							editorVariant="none"
							className="h-auto [&_[data-slate-editor]]:!min-h-0 [&_[data-slate-editor]>*:first-child]:!mt-0"
						/>
					</div>
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
								disabled={!selectedAccountId || !isTitleValid || isPanelOpen}
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
				<p className="text-sm font-semibold text-destructive">Notion authentication expired</p>
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
				<p className="text-sm font-semibold text-destructive">Failed to create Notion page</p>
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
					{result.message || "Notion page created successfully"}
				</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4 space-y-2 text-xs">
				<div>
					<span className="font-medium text-muted-foreground">Title: </span>
					<span>{result.title}</span>
				</div>
				{result.url && (
					<div>
						<a
							href={result.url}
							target="_blank"
							rel="noopener noreferrer"
							className="text-primary hover:underline"
						>
							Open in Notion
						</a>
					</div>
				)}
			</div>
		</div>
	);
}

export const CreateNotionPageToolUI = ({
	args,
	result,
}: ToolCallMessagePartProps<{ title: string; content: string }, CreateNotionPageResult>) => {
	if (!result) return null;

	if (isInterruptResult(result)) {
		return (
			<ApprovalCard
				args={args}
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

	if (isAuthErrorResult(result)) {
		return <AuthErrorCard result={result} />;
	}

	if (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as { status: string }).status === "rejected"
	) {
		return null;
	}

	if (isErrorResult(result)) {
		return <ErrorCard result={result} />;
	}

	return <SuccessCard result={result as SuccessResult} />;
};
