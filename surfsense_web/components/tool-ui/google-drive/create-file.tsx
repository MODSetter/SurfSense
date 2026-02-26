"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
	AlertTriangleIcon,
	CheckIcon,
	FileIcon,
	Loader2Icon,
	PencilIcon,
	RefreshCwIcon,
	XIcon,
} from "lucide-react";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { authenticatedFetch } from "@/lib/auth-utils";

interface GoogleDriveAccount {
	id: number;
	name: string;
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
		accounts?: GoogleDriveAccount[];
		supported_types?: string[];
		error?: string;
	};
}

interface SuccessResult {
	status: "success";
	file_id: string;
	name: string;
	web_view_link?: string;
	message?: string;
}

interface ErrorResult {
	status: "error";
	message: string;
}

interface InsufficientPermissionsResult {
	status: "insufficient_permissions";
	connector_id: number;
	message: string;
}

type CreateGoogleDriveFileResult =
	| InterruptResult
	| SuccessResult
	| ErrorResult
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

function isInsufficientPermissionsResult(result: unknown): result is InsufficientPermissionsResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as InsufficientPermissionsResult).status === "insufficient_permissions"
	);
}

const FILE_TYPE_LABELS: Record<string, string> = {
	google_doc: "Google Doc",
	google_sheet: "Google Sheet",
};

function ApprovalCard({
	args,
	interruptData,
	onDecision,
}: {
	args: { name: string; file_type: string; content?: string };
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
	const [isEditing, setIsEditing] = useState(false);
	const [editedName, setEditedName] = useState(args.name ?? "");
	const [editedContent, setEditedContent] = useState(args.content ?? "");
	const [committedArgs, setCommittedArgs] = useState<{
		name: string;
		file_type: string;
		content?: string | null;
	} | null>(null);

	const accounts = interruptData.context?.accounts ?? [];

	const defaultAccountId = useMemo(() => {
		if (accounts.length === 1) return String(accounts[0].id);
		return "";
	}, [accounts]);

	const [selectedAccountId, setSelectedAccountId] = useState<string>(defaultAccountId);
	const [selectedFileType, setSelectedFileType] = useState<string>(args.file_type ?? "google_doc");
	const [parentFolderId, setParentFolderId] = useState<string>("");

	const isNameValid = useMemo(
		() => (isEditing ? editedName.trim().length > 0 : args.name?.trim().length > 0),
		[isEditing, editedName, args.name]
	);

	const canApprove = !!selectedAccountId && isNameValid;

	const reviewConfig = interruptData.review_configs[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	function buildFinalArgs() {
		return {
			name: isEditing ? editedName : args.name,
			file_type: selectedFileType,
			content: isEditing ? editedContent || null : (args.content ?? null),
			connector_id: selectedAccountId ? Number(selectedAccountId) : null,
			parent_folder_id: parentFolderId.trim() || null,
		};
	}

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
					<p className="text-sm font-medium text-foreground">Create Google Drive File</p>
					<p className="truncate text-xs text-muted-foreground">
						{isEditing ? "You can edit the arguments below" : "Requires your approval to proceed"}
					</p>
				</div>
			</div>

			{/* Context section */}
			{!decided && interruptData.context && (
				<div className="border-b border-border px-4 py-3 bg-muted/30 space-y-3">
					{interruptData.context.error ? (
						<p className="text-sm text-destructive">{interruptData.context.error}</p>
					) : (
						<>
							{accounts.length > 0 && (
								<div className="space-y-1.5">
									<div className="text-xs font-medium text-muted-foreground">
										Google Drive Account <span className="text-destructive">*</span>
									</div>
									<Select value={selectedAccountId} onValueChange={setSelectedAccountId}>
										<SelectTrigger className="w-full">
											<SelectValue placeholder="Select an account" />
										</SelectTrigger>
										<SelectContent>
											{accounts.map((account) => (
												<SelectItem key={account.id} value={String(account.id)}>
													{account.name}
												</SelectItem>
											))}
										</SelectContent>
									</Select>
								</div>
							)}

							<div className="space-y-1.5">
								<div className="text-xs font-medium text-muted-foreground">
									File Type <span className="text-destructive">*</span>
								</div>
								<Select value={selectedFileType} onValueChange={setSelectedFileType}>
									<SelectTrigger className="w-full">
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										<SelectItem value="google_doc">Google Doc</SelectItem>
										<SelectItem value="google_sheet">Google Sheet</SelectItem>
									</SelectContent>
								</Select>
							</div>

							<div className="space-y-1.5">
								<div className="text-xs font-medium text-muted-foreground">
									Parent Folder ID (optional)
								</div>
								<Input
									value={parentFolderId}
									onChange={(e) => setParentFolderId(e.target.value)}
									placeholder="Leave blank to create at Drive root"
								/>
								<p className="text-xs text-muted-foreground">
									Paste a Google Drive folder ID to place the file in a specific folder.
								</p>
							</div>
						</>
					)}
				</div>
			)}

			{/* Display mode */}
			{!isEditing && (
				<div className="space-y-2 px-4 py-3 bg-card">
					<div>
						<p className="text-xs font-medium text-muted-foreground">Name</p>
						<p className="text-sm text-foreground">{committedArgs?.name ?? args.name}</p>
					</div>
					<div>
						<p className="text-xs font-medium text-muted-foreground">Type</p>
						<p className="text-sm text-foreground">
							{FILE_TYPE_LABELS[committedArgs?.file_type ?? args.file_type] ??
								committedArgs?.file_type ??
								args.file_type}
						</p>
					</div>
					{(committedArgs?.content ?? args.content) && (
						<div>
							<p className="text-xs font-medium text-muted-foreground">Content</p>
							<p className="line-clamp-4 text-sm whitespace-pre-wrap text-foreground">
								{committedArgs?.content ?? args.content}
							</p>
						</div>
					)}
				</div>
			)}

			{/* Edit mode */}
			{isEditing && !decided && (
				<div className="space-y-3 px-4 py-3 bg-card">
					<div>
						<label
							htmlFor="gdrive-name"
							className="text-xs font-medium text-muted-foreground mb-1.5 block"
						>
							Name <span className="text-destructive">*</span>
						</label>
						<Input
							id="gdrive-name"
							value={editedName}
							onChange={(e) => setEditedName(e.target.value)}
							placeholder="Enter file name"
							className={!isNameValid ? "border-destructive" : ""}
						/>
						{!isNameValid && <p className="text-xs text-destructive mt-1">Name is required</p>}
					</div>
					<div>
						<label
							htmlFor="gdrive-content"
							className="text-xs font-medium text-muted-foreground mb-1.5 block"
						>
							{selectedFileType === "google_sheet" ? "Content (CSV)" : "Content (Markdown)"}
						</label>
						<Textarea
							id="gdrive-content"
							value={editedContent}
							onChange={(e) => setEditedContent(e.target.value)}
							placeholder={
								selectedFileType === "google_sheet"
									? "Column A,Column B\nValue 1,Value 2"
									: "# Heading\n\nYour content here..."
							}
							rows={6}
							className="resize-none font-mono text-xs"
						/>
					</div>
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
						{decided === "approve" || decided === "edit" ? (
							<>
								<CheckIcon className="size-3.5 text-green-500" />
								{decided === "edit" ? "Approved with Changes" : "Approved"}
							</>
						) : (
							<>
								<XIcon className="size-3.5 text-destructive" />
								Rejected
							</>
						)}
					</p>
				) : isEditing ? (
					<>
						<Button
							size="sm"
							onClick={() => {
								const finalArgs = buildFinalArgs();
								setCommittedArgs(finalArgs);
								setDecided("edit");
								setIsEditing(false);
								onDecision({
									type: "edit",
									edited_action: {
										name: interruptData.action_requests[0].name,
										args: finalArgs,
									},
								});
							}}
							disabled={!canApprove}
						>
							<CheckIcon />
							Approve with Changes
						</Button>
						<Button
							size="sm"
							variant="outline"
							onClick={() => {
								setIsEditing(false);
								setEditedName(args.name ?? "");
								setEditedContent(args.content ?? "");
							}}
						>
							Cancel
						</Button>
					</>
				) : (
					<>
						{allowedDecisions.includes("approve") && (
							<Button
								size="sm"
								onClick={() => {
									const finalArgs = buildFinalArgs();
									setCommittedArgs(finalArgs);
									setDecided("approve");
									onDecision({
										type: "approve",
										edited_action: {
											name: interruptData.action_requests[0].name,
											args: finalArgs,
										},
									});
								}}
								disabled={!canApprove}
							>
								<CheckIcon />
								Approve
							</Button>
						)}
						{canEdit && (
							<Button size="sm" variant="outline" onClick={() => setIsEditing(true)}>
								<PencilIcon />
								Edit
							</Button>
						)}
						{allowedDecisions.includes("reject") && (
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
						)}
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

function ErrorCard({ result }: { result: ErrorResult }) {
	return (
		<div className="my-4 max-w-md overflow-hidden rounded-xl border border-destructive/50 bg-card">
			<div className="flex items-center gap-3 border-b border-destructive/50 px-4 py-3">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-destructive/10">
					<XIcon className="size-4 text-destructive" />
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-sm font-medium text-destructive">Failed to create Google Drive file</p>
				</div>
			</div>
			<div className="px-4 py-3">
				<p className="text-sm text-muted-foreground">{result.message}</p>
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
						{result.message || "Google Drive file created successfully"}
					</p>
				</div>
			</div>
			<div className="space-y-2 px-4 py-3 text-xs">
				<div className="flex items-center gap-1.5">
					<FileIcon className="size-3.5 text-muted-foreground" />
					<span className="font-medium">{result.name}</span>
				</div>
				{result.web_view_link && (
					<div>
						<a
							href={result.web_view_link}
							target="_blank"
							rel="noopener noreferrer"
							className="text-primary hover:underline"
						>
							Open in Google Drive
						</a>
					</div>
				)}
			</div>
		</div>
	);
}

export const CreateGoogleDriveFileToolUI = makeAssistantToolUI<
	{ name: string; file_type: string; content?: string },
	CreateGoogleDriveFileResult
>({
	toolName: "create_google_drive_file",
	render: function CreateGoogleDriveFileUI({ args, result, status }) {
		if (status.type === "running") {
			return (
				<div className="my-4 flex max-w-md items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
					<Loader2Icon className="size-4 animate-spin text-muted-foreground" />
					<p className="text-sm text-muted-foreground">Preparing Google Drive file...</p>
				</div>
			);
		}

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

		if (isInsufficientPermissionsResult(result))
			return <InsufficientPermissionsCard result={result} />;

		if (isErrorResult(result)) return <ErrorCard result={result} />;

		return <SuccessCard result={result as SuccessResult} />;
	},
});
