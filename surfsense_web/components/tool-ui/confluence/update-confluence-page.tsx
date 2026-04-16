"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useSetAtom } from "jotai";
import { CornerDownLeftIcon, Pen } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { openHitlEditPanelAtom } from "@/atoms/chat/hitl-edit-panel.atom";
import { PlateEditor } from "@/components/editor/plate-editor";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import { useHitlPhase } from "@/hooks/use-hitl-phase";
import type { HitlDecision, InterruptResult } from "@/lib/hitl";
import { isInterruptResult, useHitlDecision } from "@/lib/hitl";

type UpdateConfluencePageInterruptContext = {
	account?: {
		id: number;
		name: string;
		base_url: string;
		auth_expired?: boolean;
	};
	page?: {
		page_id: string;
		page_title: string;
		space_id: string;
		body: string;
		version: number;
		document_id: number;
		indexed_at?: string;
	};
	error?: string;
};

interface SuccessResult {
	status: "success";
	page_id: string;
	page_url?: string;
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

type UpdateConfluencePageResult =
	| InterruptResult<UpdateConfluencePageInterruptContext>
	| SuccessResult
	| ErrorResult
	| NotFoundResult
	| AuthErrorResult
	| InsufficientPermissionsResult;

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
		page_title_or_id: string;
		new_title?: string;
		new_content?: string;
	};
	interruptData: InterruptResult<UpdateConfluencePageInterruptContext>;
	onDecision: (decision: HitlDecision) => void;
}) {
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);

	const actionArgs = interruptData.action_requests[0]?.args ?? {};
	const context = interruptData.context;
	const page = context?.page;

	const [isPanelOpen, setIsPanelOpen] = useState(false);
	const [editedArgs, setEditedArgs] = useState(() => ({
		title: actionArgs.new_title
			? String(actionArgs.new_title)
			: (page?.page_title ?? args.new_title ?? ""),
		content: actionArgs.new_content
			? String(actionArgs.new_content)
			: (page?.body ?? args.new_content ?? ""),
	}));
	const [hasPanelEdits, setHasPanelEdits] = useState(false);
	const openHitlEditPanel = useSetAtom(openHitlEditPanelAtom);

	const reviewConfig = interruptData.review_configs[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	const hasProposedChanges =
		actionArgs.new_title || args.new_title || actionArgs.new_content || args.new_content;

	const buildFinalArgs = useCallback(() => {
		return {
			page_id: page?.page_id,
			document_id: page?.document_id,
			connector_id: context?.account?.id,
			new_title: editedArgs.title || null,
			new_content: editedArgs.content || null,
			version: page?.version,
		};
	}, [page?.page_id, page?.document_id, page?.version, context?.account?.id, editedArgs]);

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
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 transition-[box-shadow] duration-300">
			{/* Header */}
			<div className="flex items-start justify-between px-5 pt-5 pb-4 select-none">
				<div>
					<p className="text-sm font-semibold text-foreground">
						{phase === "rejected"
							? "Confluence Page Update Rejected"
							: phase === "processing" || phase === "complete"
								? "Confluence Page Update Approved"
								: "Update Confluence Page"}
					</p>
					{phase === "processing" ? (
						<TextShimmerLoader
							text={hasPanelEdits ? "Updating page with your changes" : "Updating page"}
							size="sm"
						/>
					) : phase === "complete" ? (
						<p className="text-xs text-muted-foreground mt-0.5">
							{hasPanelEdits ? "Page updated with your changes" : "Page updated"}
						</p>
					) : phase === "rejected" ? (
						<p className="text-xs text-muted-foreground mt-0.5">Page update was cancelled</p>
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
								title: editedArgs.title,
								content: editedArgs.content,
								toolName: "Confluence Page",
								contentFormat: "html",
								onSave: (newTitle, newContent) => {
									setIsPanelOpen(false);
									setEditedArgs({
										title: newTitle,
										content: newContent,
									});
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

			{/* Context section — account + current page (visible in pending) */}
			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 space-y-4 select-none">
						{context?.error ? (
							<p className="text-sm text-destructive">{context.error}</p>
						) : (
							<>
								{context?.account && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">Confluence Account</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm">
											{context.account.name}
										</div>
									</div>
								)}

								{page && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">Current Page</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm space-y-1.5">
											<div className="font-medium">{page.page_title}</div>
											{page.body && (
												<div
													className="max-h-[5rem] overflow-hidden text-xs text-muted-foreground"
													style={{
														maskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
														WebkitMaskImage:
															"linear-gradient(to bottom, black 50%, transparent 100%)",
													}}
												>
													<PlateEditor
														html={page.body}
														readOnly
														preset="readonly"
														editorVariant="none"
														className="h-auto [&_[data-slate-editor]]:!min-h-0 [&_[data-slate-editor]>*:first-child]:!mt-0"
													/>
												</div>
											)}
											{page.space_id && (
												<div className="text-xs text-muted-foreground">Space: {page.space_id}</div>
											)}
										</div>
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
						{(hasPanelEdits ? editedArgs.title : (actionArgs.new_title ?? args.new_title)) && (
							<p className="text-sm font-medium text-foreground">
								{String(
									hasPanelEdits ? editedArgs.title : (actionArgs.new_title ?? args.new_title)
								)}
							</p>
						)}
						{(hasPanelEdits
							? editedArgs.content
							: (actionArgs.new_content ?? args.new_content)) && (
							<div
								className="max-h-[7rem] overflow-hidden text-sm"
								style={{
									maskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
									WebkitMaskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
								}}
							>
								<PlateEditor
									html={String(
										hasPanelEdits
											? editedArgs.content
											: (actionArgs.new_content ?? args.new_content)
									)}
									readOnly
									preset="readonly"
									editorVariant="none"
									className="h-auto [&_[data-slate-editor]]:!min-h-0 [&_[data-slate-editor]>*:first-child]:!mt-0"
								/>
							</div>
						)}
					</>
				) : (
					<p className="text-sm text-muted-foreground italic pb-3">No changes proposed</p>
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
				<p className="text-sm font-semibold text-destructive">Confluence authentication expired</p>
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
					Additional Confluence permissions required
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
				<p className="text-sm font-semibold text-destructive">Failed to update Confluence page</p>
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
				<p className="text-sm font-semibold text-amber-600 dark:text-amber-400">Page not found</p>
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
					{result.message || "Confluence page updated successfully"}
				</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4 space-y-2 text-xs">
				{result.page_url ? (
					<a
						href={result.page_url}
						target="_blank"
						rel="noopener noreferrer"
						className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
					>
						Open in Confluence
					</a>
				) : (
					<div>
						<span className="font-medium text-muted-foreground">Page ID: </span>
						<span>{result.page_id}</span>
					</div>
				)}
			</div>
		</div>
	);
}

export const UpdateConfluencePageToolUI = ({
	args,
	result,
}: ToolCallMessagePartProps<
	{
		page_title_or_id: string;
		new_title?: string;
		new_content?: string;
	},
	UpdateConfluencePageResult
>) => {
	const { dispatch } = useHitlDecision();

	if (!result) return null;

	if (isInterruptResult(result)) {
		return (
			<ApprovalCard
				args={args}
				interruptData={result as InterruptResult<UpdateConfluencePageInterruptContext>}
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

	if (isNotFoundResult(result)) return <NotFoundCard result={result} />;
	if (isAuthErrorResult(result)) return <AuthErrorCard result={result} />;
	if (isInsufficientPermissionsResult(result))
		return <InsufficientPermissionsCard result={result} />;
	if (isErrorResult(result)) return <ErrorCard result={result} />;

	return <SuccessCard result={result as SuccessResult} />;
};
