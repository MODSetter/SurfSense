"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
	AlertTriangleIcon,
	CheckIcon,
	InfoIcon,
	Loader2Icon,
	RefreshCwIcon,
	Trash2Icon,
	XIcon,
} from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { authenticatedFetch } from "@/lib/auth-utils";

interface GoogleDriveAccount {
	id: number;
	name: string;
}

interface GoogleDriveFile {
	file_id: string;
	name: string;
	mime_type: string;
	web_view_link: string;
}

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
	context?: {
		account?: GoogleDriveAccount;
		file?: GoogleDriveFile;
		error?: string;
	};
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

type DeleteGoogleDriveFileResult =
	| InterruptResult
	| SuccessResult
	| WarningResult
	| ErrorResult
	| NotFoundResult
	| InsufficientPermissionsResult;

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

function isInsufficientPermissionsResult(result: unknown): result is InsufficientPermissionsResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as InsufficientPermissionsResult).status === "insufficient_permissions"
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
	interruptData: InterruptResult;
	onDecision: (decision: {
		type: "approve" | "reject";
		message?: string;
		edited_action?: { name: string; args: Record<string, unknown> };
	}) => void;
}) {
	const [decided, setDecided] = useState<"approve" | "reject" | null>(
		interruptData.__decided__ ?? null
	);
	const [deleteFromKb, setDeleteFromKb] = useState(false);

	const account = interruptData.context?.account;
	const file = interruptData.context?.file;
	const fileLabel = file?.mime_type ? (MIME_TYPE_LABELS[file.mime_type] ?? "File") : "File";

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
					<p className="text-sm font-medium text-foreground">Delete Google Drive File</p>
					<p className="truncate text-xs text-muted-foreground">
						Requires your approval to proceed
					</p>
				</div>
			</div>

			{/* Context — read-only file details */}
			{!decided && interruptData.context && (
				<div className="border-b border-border px-4 py-3 bg-muted/30 space-y-3">
					{interruptData.context.error ? (
						<p className="text-sm text-destructive">{interruptData.context.error}</p>
					) : (
						<>
							{account && (
								<div className="space-y-1.5">
									<div className="text-xs font-medium text-muted-foreground">
										Google Drive Account
									</div>
									<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm">
										{account.name}
									</div>
								</div>
							)}

							{file && (
								<div className="space-y-1.5">
									<div className="text-xs font-medium text-muted-foreground">File to Trash</div>
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
			)}

			{/* Trash warning */}
			{!decided && (
				<div className="px-4 py-3 border-b border-border bg-muted/20">
					<p className="text-xs text-muted-foreground">
						⚠️ The file will be moved to Google Drive trash. You can restore it from trash within 30
						days.
					</p>
				</div>
			)}

			{/* Checkbox for deleting from knowledge base */}
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
								⚠️ This will permanently delete the file from your knowledge base (cannot be undone)
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
							variant="destructive"
							onClick={() => {
								setDecided("approve");
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
							}}
						>
							<Trash2Icon />
							Move to Trash
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

function InsufficientPermissionsCard({ result }: { result: InsufficientPermissionsResult }) {
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [loading, setLoading] = useState(false);

	async function handleReauth() {
		setLoading(true);
		try {
			const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";
			const url = new URL(`${backendUrl}/api/v1/auth/google/drive/connector/reauth`);
			url.searchParams.set("connector_id", String(result.connector_id));
			url.searchParams.set("space_id", searchSpaceId);
			url.searchParams.set("return_url", window.location.pathname);
			const response = await authenticatedFetch(url.toString());
			if (!response.ok) {
				const data = await response.json().catch(() => ({}));
				toast.error(data.detail ?? "Failed to initiate re-authentication. Please try again.");
				return;
			}
			const data = await response.json();
			if (data.auth_url) {
				window.location.href = data.auth_url;
			}
		} catch {
			toast.error("Failed to initiate re-authentication. Please try again.");
		} finally {
			setLoading(false);
		}
	}

	return (
		<div className="my-4 max-w-md overflow-hidden rounded-xl border border-amber-500/50 bg-card">
			<div className="flex items-center gap-3 border-b border-amber-500/50 px-4 py-3">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-amber-500/10">
					<AlertTriangleIcon className="size-4 text-amber-500" />
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-sm font-medium text-amber-600 dark:text-amber-400">
						Additional permissions required
					</p>
				</div>
			</div>
			<div className="space-y-3 px-4 py-3">
				<p className="text-sm text-muted-foreground">{result.message}</p>
				<Button size="sm" onClick={handleReauth} disabled={loading}>
					{loading ? (
						<Loader2Icon className="size-4 animate-spin" />
					) : (
						<RefreshCwIcon className="size-4" />
					)}
					Re-authenticate Google Drive
				</Button>
			</div>
		</div>
	);
}

function WarningCard({ result }: { result: WarningResult }) {
	return (
		<div className="my-4 max-w-md overflow-hidden rounded-xl border border-amber-500/50 bg-card">
			<div className="flex items-center gap-3 border-b border-amber-500/50 px-4 py-3">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-amber-500/10">
					<AlertTriangleIcon className="size-4 text-amber-500" />
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-sm font-medium text-amber-600 dark:text-amber-500">Partial success</p>
				</div>
			</div>
			<div className="space-y-2 px-4 py-3">
				{result.message && <p className="text-sm text-muted-foreground">{result.message}</p>}
				<p className="text-xs text-amber-600 dark:text-amber-500">{result.warning}</p>
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
					<p className="text-sm font-medium text-destructive">Failed to delete file</p>
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

function SuccessCard({ result }: { result: SuccessResult }) {
	return (
		<div className="my-4 max-w-md overflow-hidden rounded-xl border border-border bg-card">
			<div className="flex items-center gap-3 border-b border-border px-4 py-3">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-green-500/10">
					<CheckIcon className="size-4 text-green-500" />
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-[.8rem] text-muted-foreground">
						{result.message || "File moved to trash successfully"}
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

export const DeleteGoogleDriveFileToolUI = makeAssistantToolUI<
	{ file_name: string; delete_from_kb?: boolean },
	DeleteGoogleDriveFileResult
>({
	toolName: "delete_google_drive_file",
	render: function DeleteGoogleDriveFileUI({ result, status }) {
		if (status.type === "running") {
			return (
				<div className="my-4 flex max-w-md items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
					<Loader2Icon className="size-4 animate-spin text-muted-foreground" />
					<p className="text-sm text-muted-foreground">Looking up file in Google Drive...</p>
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

		if (isInsufficientPermissionsResult(result))
			return <InsufficientPermissionsCard result={result} />;

		if (isNotFoundResult(result)) return <NotFoundCard result={result} />;
		if (isWarningResult(result)) return <WarningCard result={result} />;
		if (isErrorResult(result)) return <ErrorCard result={result} />;

		return <SuccessCard result={result as SuccessResult} />;
	},
});
