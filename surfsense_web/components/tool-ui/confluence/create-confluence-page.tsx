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
import type { HitlDecision, InterruptResult } from "@/lib/hitl";
import { isInterruptResult, useHitlDecision } from "@/lib/hitl";

interface ConfluenceAccount {
	id: number;
	name: string;
	base_url: string;
	auth_expired?: boolean;
}

interface ConfluenceSpace {
	id: string;
	key: string;
	name: string;
}

type CreateConfluencePageInterruptContext = {
	accounts?: ConfluenceAccount[];
	spaces?: ConfluenceSpace[];
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

type CreateConfluencePageResult =
	| InterruptResult<CreateConfluencePageInterruptContext>
	| SuccessResult
	| ErrorResult
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
	args: { title: string; content?: string; space_id?: string };
	interruptData: InterruptResult<CreateConfluencePageInterruptContext>;
	onDecision: (decision: HitlDecision) => void;
}) {
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);
	const [isPanelOpen, setIsPanelOpen] = useState(false);
	const openHitlEditPanel = useSetAtom(openHitlEditPanelAtom);
	const [pendingEdits, setPendingEdits] = useState<{ title: string; content: string } | null>(null);

	const [selectedAccountId, setSelectedAccountId] = useState("");
	const [selectedSpaceId, setSelectedSpaceId] = useState("");

	const accounts = interruptData.context?.accounts ?? [];
	const spaces = interruptData.context?.spaces ?? [];
	const validAccounts = useMemo(() => accounts.filter((a) => !a.auth_expired), [accounts]);
	const expiredAccounts = useMemo(() => accounts.filter((a) => a.auth_expired), [accounts]);

	const isTitleValid = (pendingEdits?.title ?? args.title ?? "").trim().length > 0;
	const canApprove = !!selectedAccountId && !!selectedSpaceId && isTitleValid;

	const reviewConfig = interruptData.review_configs[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	const buildFinalArgs = useCallback(
		(overrides?: { title?: string; content?: string }) => {
			return {
				title: overrides?.title ?? pendingEdits?.title ?? args.title,
				content: overrides?.content ?? pendingEdits?.content ?? args.content ?? null,
				connector_id: selectedAccountId ? Number(selectedAccountId) : null,
				space_id: selectedSpaceId || null,
			};
		},
		[args.title, args.content, selectedAccountId, selectedSpaceId, pendingEdits]
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
							? "Confluence Page Rejected"
							: phase === "processing" || phase === "complete"
								? "Confluence Page Approved"
								: "Create Confluence Page"}
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
								title: pendingEdits?.title ?? args.title ?? "",
								content: pendingEdits?.content ?? args.content ?? "",
								toolName: "Confluence Page",
								contentFormat: "html",
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

			{/* Context section — account + space pickers in pending */}
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
											Confluence Account <span className="text-destructive">*</span>
										</p>
										<Select
											value={selectedAccountId}
											onValueChange={(v) => {
												setSelectedAccountId(v);
												setSelectedSpaceId("");
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

								{selectedAccountId && spaces.length > 0 && (
									<div className="space-y-1.5">
										<p className="text-xs font-medium text-muted-foreground">
											Space <span className="text-destructive">*</span>
										</p>
										<Select value={selectedSpaceId} onValueChange={setSelectedSpaceId}>
											<SelectTrigger className="w-full">
												<SelectValue placeholder="Select a space" />
											</SelectTrigger>
											<SelectContent>
												{spaces.map((s) => (
													<SelectItem key={s.id} value={s.id}>
														{s.name} ({s.key})
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

			{/* Content preview */}
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 pt-3">
				{(pendingEdits?.title ?? args.title) != null && (
					<p className="text-sm font-medium text-foreground">{pendingEdits?.title ?? args.title}</p>
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
							html={pendingEdits?.content ?? args.content ?? ""}
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
				<p className="text-sm font-semibold text-destructive">All Confluence accounts expired</p>
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
				<p className="text-sm font-semibold text-destructive">Failed to create Confluence page</p>
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
					{result.message || "Confluence page created successfully"}
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

export const CreateConfluencePageToolUI = ({
	args,
	result,
}: ToolCallMessagePartProps<
	{ title: string; content?: string; space_id?: string },
	CreateConfluencePageResult
>) => {
	const { dispatch } = useHitlDecision();

	if (!result) return null;

	if (isInterruptResult(result)) {
		return (
			<ApprovalCard
				args={args}
				interruptData={result as InterruptResult<CreateConfluencePageInterruptContext>}
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
