"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { CornerDownLeftIcon, InfoIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useHitlPhase } from "@/hooks/use-hitl-phase";
import { isInterruptResult, useHitlDecision } from "@/lib/hitl";
import type { InterruptResult, HitlDecision } from "@/lib/hitl";

interface GoogleDriveAccount {
	id: number;
	name: string;
	auth_expired?: boolean;
}

interface GoogleDriveFile {
	file_id: string;
	name: string;
	mime_type: string;
	web_view_link: string;
}

interface DriveTrashFileContext {
	account?: GoogleDriveAccount;
	file?: GoogleDriveFile;
	error?: string;
}

interface SuccessResult {
	status: "success";
	file_id: string;
	message?: string;
	deleted_from_kb?: boolean;
}

interface WarningResult {
	status: "success";
	warning: string;
	file_id?: string;
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

interface InsufficientPermissionsResult {
	status: "insufficient_permissions";
	connector_id: number;
	message: string;
}

interface AuthErrorResult {
	status: "auth_error";
	message: string;
	connector_type?: string;
}

type DeleteGoogleDriveFileResult =
	| InterruptResult<DriveTrashFileContext>
	| SuccessResult
	| WarningResult
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

function isInsufficientPermissionsResult(result: unknown): result is InsufficientPermissionsResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as InsufficientPermissionsResult).status === "insufficient_permissions"
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

const MIME_TYPE_LABELS: Record<string, string> = {
	"application/vnd.google-apps.document": "Google Doc",
	"application/vnd.google-apps.spreadsheet": "Google Sheet",
	"application/vnd.google-apps.presentation": "Google Slides",
};

function ApprovalCard({
	interruptData,
	onDecision,
}: {
	interruptData: InterruptResult<DriveTrashFileContext>;
	onDecision: (decision: HitlDecision) => void;
}) {
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);
	const [deleteFromKb, setDeleteFromKb] = useState(false);

	const context = interruptData.context;
	const account = context?.account;
	const file = context?.file;
	const fileLabel = file?.mime_type ? (MIME_TYPE_LABELS[file.mime_type] ?? "File") : "File";

	const handleApprove = useCallback(() => {
		if (phase !== "pending") return;
		setProcessing();
		onDecision({
			type: "approve",
			edited_action: {
				name: interruptData.action_requests[0].name,
				args: {
					file_id: file?.file_id,
					connector_id: account?.id,
					delete_from_kb: deleteFromKb,
				},
			},
		});
	}, [phase, setProcessing, onDecision, interruptData, file?.file_id, account?.id, deleteFromKb]);

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
							? "Google Drive File Deletion Rejected"
							: phase === "processing" || phase === "complete"
								? "Google Drive File Deletion Approved"
								: "Delete Google Drive File"}
					</p>
					{phase === "processing" ? (
						<TextShimmerLoader text="Trashing file" size="sm" />
					) : phase === "complete" ? (
						<p className="text-xs text-muted-foreground mt-0.5">File trashed</p>
					) : phase === "rejected" ? (
						<p className="text-xs text-muted-foreground mt-0.5">File deletion was cancelled</p>
					) : (
						<p className="text-xs text-muted-foreground mt-0.5">
							Requires your approval to proceed
						</p>
					)}
				</div>
			</div>

			{/* Context — read-only file details (visible in pending, processing, complete) */}
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
										<p className="text-xs font-medium text-muted-foreground">
											Google Drive Account
										</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm">
											{account.name}
										</div>
									</div>
								)}

								{file && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">File to Trash</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm space-y-0.5">
											<div className="font-medium">{file.name}</div>
											<div className="text-xs text-muted-foreground">{fileLabel}</div>
											{file.web_view_link && (
												<a
													href={file.web_view_link}
													target="_blank"
													rel="noopener noreferrer"
													className="text-xs text-primary hover:underline"
												>
													Open in Drive
												</a>
											)}
										</div>
									</div>
								)}
							</>
						)}
					</div>
				</>
			)}

			{/* Trash warning + delete_from_kb toggle */}
			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 space-y-3 select-none">
						<p className="text-xs text-muted-foreground">
							The file will be moved to Google Drive trash. You can restore it from trash within 30
							days.
						</p>
						<div className="flex items-center gap-2.5">
							<Checkbox
								id="delete-from-kb"
								checked={deleteFromKb}
								onCheckedChange={(v) => setDeleteFromKb(v === true)}
								className="shrink-0"
							/>
							<label htmlFor="delete-from-kb" className="flex-1 cursor-pointer">
								<span className="text-sm text-foreground">Also remove from knowledge base</span>
								<p className="text-xs text-muted-foreground mt-0.5">
									This will permanently delete the file from your knowledge base (cannot be undone)
								</p>
							</label>
						</div>
					</div>
				</>
			)}

			{/* Action buttons - only shown when pending */}
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

function InsufficientPermissionsCard({ result }: { result: InsufficientPermissionsResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">
					Additional Google Drive permissions required
				</p>
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
					Google Drive authentication expired
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
				<p className="text-sm font-medium text-amber-600 dark:text-amber-500">Partial success</p>
			</div>
			<div className="px-5 py-4 space-y-2">
				{result.message && <p className="text-sm text-muted-foreground">{result.message}</p>}
				<p className="text-xs text-amber-600 dark:text-amber-500">{result.warning}</p>
			</div>
		</div>
	);
}

function ErrorCard({ result }: { result: ErrorResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">Failed to delete file</p>
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
			<div className="flex items-start gap-3 px-5 py-4">
				<InfoIcon className="size-4 mt-0.5 shrink-0 text-muted-foreground" />
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
					{result.message || "File moved to trash successfully"}
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

export const DeleteGoogleDriveFileToolUI = ({
	result,
}: ToolCallMessagePartProps<
	{ file_name: string; delete_from_kb?: boolean },
	DeleteGoogleDriveFileResult
>) => {
	const { dispatch } = useHitlDecision();
	if (!result) return null;

	if (isInterruptResult(result)) {
		return (
			<ApprovalCard
				interruptData={result as InterruptResult<DriveTrashFileContext>}
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
	if (isWarningResult(result)) return <WarningCard result={result} />;
	if (isErrorResult(result)) return <ErrorCard result={result} />;

	return <SuccessCard result={result as SuccessResult} />;
};
