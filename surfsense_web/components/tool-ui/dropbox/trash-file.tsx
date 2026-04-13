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

interface DropboxAccount {
	id: number;
	name: string;
	user_email?: string;
	auth_expired?: boolean;
}

interface DropboxFile {
	file_id: string;
	file_path: string;
	name: string;
	document_id?: number;
}

type DropboxTrashFileContext = {
	account?: DropboxAccount;
	file?: DropboxFile;
	error?: string;
}

interface SuccessResult {
	status: "success";
	file_id: string;
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

type DeleteDropboxFileResult =
	| InterruptResult<DropboxTrashFileContext>
	| SuccessResult
	| ErrorResult
	| NotFoundResult
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

function ApprovalCard({
	interruptData,
	onDecision,
}: {
	interruptData: InterruptResult<DropboxTrashFileContext>;
	onDecision: (decision: HitlDecision) => void;
}) {
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);
	const [deleteFromKb, setDeleteFromKb] = useState(false);

	const context = interruptData.context;
	const account = context?.account;
	const file = context?.file;

	const handleApprove = useCallback(() => {
		if (phase !== "pending") return;
		setProcessing();
		onDecision({
			type: "approve",
			edited_action: {
				name: interruptData.action_requests[0].name,
				args: {
					file_path: file?.file_path,
					connector_id: account?.id,
					delete_from_kb: deleteFromKb,
				},
			},
		});
	}, [phase, setProcessing, onDecision, interruptData, file?.file_path, account?.id, deleteFromKb]);

	useEffect(() => {
		const handler = (e: KeyboardEvent) => {
			if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey) handleApprove();
		};
		window.addEventListener("keydown", handler);
		return () => window.removeEventListener("keydown", handler);
	}, [handleApprove]);

	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 transition-[box-shadow] duration-300">
			<div className="flex items-start justify-between px-5 pt-5 pb-4 select-none">
				<div>
					<p className="text-sm font-semibold text-foreground">
						{phase === "rejected"
							? "Dropbox File Deletion Rejected"
							: phase === "processing" || phase === "complete"
								? "Dropbox File Deletion Approved"
								: "Delete Dropbox File"}
					</p>
					{phase === "processing" ? (
						<TextShimmerLoader text="Deleting file" size="sm" />
					) : phase === "complete" ? (
						<p className="text-xs text-muted-foreground mt-0.5">File deleted</p>
					) : phase === "rejected" ? (
						<p className="text-xs text-muted-foreground mt-0.5">File deletion was cancelled</p>
					) : (
						<p className="text-xs text-muted-foreground mt-0.5">
							Requires your approval to proceed
						</p>
					)}
				</div>
			</div>

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
										<p className="text-xs font-medium text-muted-foreground">Dropbox Account</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm">
											{account.name}
										</div>
									</div>
								)}
								{file && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">File to Delete</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm space-y-0.5">
											<div className="font-medium">{file.name}</div>
											{file.file_path && (
												<div className="text-xs text-muted-foreground">{file.file_path}</div>
											)}
										</div>
									</div>
								)}
							</>
						)}
					</div>
				</>
			)}

			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 space-y-3 select-none">
						<p className="text-xs text-muted-foreground">
							The file will be permanently deleted from Dropbox.
						</p>
						<div className="flex items-center gap-2.5">
							<Checkbox
								id="db-delete-from-kb"
								checked={deleteFromKb}
								onCheckedChange={(v) => setDeleteFromKb(v === true)}
								className="shrink-0"
							/>
							<label htmlFor="db-delete-from-kb" className="flex-1 cursor-pointer">
								<span className="text-sm text-foreground">Also remove from knowledge base</span>
								<p className="text-xs text-muted-foreground mt-0.5">
									This will permanently delete the file from your knowledge base
								</p>
							</label>
						</div>
					</div>
				</>
			)}

			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 flex items-center gap-2 select-none">
						<Button size="sm" className="rounded-lg gap-1.5" onClick={handleApprove}>
							Approve <CornerDownLeftIcon className="size-3 opacity-60" />
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

function AuthErrorCard({ result }: { result: AuthErrorResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">Dropbox authentication expired</p>
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
					{result.message || "File deleted from Dropbox"}
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

export const DeleteDropboxFileToolUI = ({
	result,
}: ToolCallMessagePartProps<
	{ file_name: string; delete_from_kb?: boolean },
	DeleteDropboxFileResult
>) => {
	const { dispatch } = useHitlDecision();
	if (!result) return null;
	if (isInterruptResult(result)) {
		return (
			<ApprovalCard
				interruptData={result as InterruptResult<DropboxTrashFileContext>}
				onDecision={(decision) => dispatch([decision])}
			/>
		);
	}
	if (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as { status: string }).status === "rejected"
	)
		return null;
	if (isAuthErrorResult(result)) return <AuthErrorCard result={result} />;
	if (isNotFoundResult(result)) return <NotFoundCard result={result} />;
	if (isErrorResult(result)) return <ErrorCard result={result} />;
	return <SuccessCard result={result as SuccessResult} />;
};
