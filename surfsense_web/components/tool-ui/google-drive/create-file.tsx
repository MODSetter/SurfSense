"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
	AlertTriangleIcon,
	CornerDownLeftIcon,
	FileIcon,
	Pen,
	RefreshCwIcon,
} from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
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
import { PlateEditor } from "@/components/editor/plate-editor";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { authenticatedFetch } from "@/lib/auth-utils";
import { useSetAtom } from "jotai";
import { openHitlEditPanelAtom } from "@/atoms/chat/hitl-edit-panel.atom";

interface GoogleDriveAccount {
	id: number;
	name: string;
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

interface AuthErrorResult {
	status: "auth_error";
	message: string;
	connector_type?: string;
}

type CreateGoogleDriveFileResult =
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
	const [isPanelOpen, setIsPanelOpen] = useState(false);
	const openHitlEditPanel = useSetAtom(openHitlEditPanelAtom);

	const accounts = interruptData.context?.accounts ?? [];
	const validAccounts = accounts.filter(a => !a.auth_expired);
	const expiredAccounts = accounts.filter(a => a.auth_expired);

	const defaultAccountId = useMemo(() => {
		if (validAccounts.length === 1) return String(validAccounts[0].id);
		return "";
	}, [validAccounts]);

	const [selectedAccountId, setSelectedAccountId] = useState<string>(defaultAccountId);
	const [selectedFileType, setSelectedFileType] = useState<string>(args.file_type ?? "google_doc");
	const [parentFolderId, setParentFolderId] = useState<string>("");

	const isNameValid = useMemo(
		() => args.name && typeof args.name === "string" && args.name.trim().length > 0,
		[args.name]
	);

	const canApprove = !!selectedAccountId && isNameValid;

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
					file_type: selectedFileType,
					connector_id: selectedAccountId ? Number(selectedAccountId) : null,
					parent_folder_id: parentFolderId.trim() || null,
				},
			},
		});
	}, [decided, isPanelOpen, canApprove, allowedDecisions, onDecision, interruptData, args, selectedFileType, selectedAccountId, parentFolderId]);

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
				<div>
					<p className="text-sm font-semibold text-foreground">
						{decided === "reject"
							? "Google Drive File Rejected"
							: decided === "approve" || decided === "edit"
								? "Google Drive File Approved"
								: "Create Google Drive File"}
					</p>
					<p className="text-xs text-muted-foreground mt-0.5">
						{decided === "reject"
							? "File creation was cancelled"
							: decided === "edit"
								? "File creation is in progress with your changes"
								: decided === "approve"
									? "File creation is in progress"
									: "Requires your approval to proceed"}
					</p>
				</div>
				{!decided && canEdit && (
					<Button
						size="sm"
						variant="ghost"
						className="rounded-lg text-muted-foreground -mt-1 -mr-2"
						onClick={() => {
							setIsPanelOpen(true);
							openHitlEditPanel({
								title: args.name ?? "",
								content: args.content ?? "",
								toolName: "Google Drive File",
								onSave: (newName, newContent) => {
									setIsPanelOpen(false);
									setDecided("edit");
									onDecision({
										type: "edit",
										edited_action: {
											name: interruptData.action_requests[0].name,
											args: {
												...args,
												name: newName,
												content: newContent,
												file_type: selectedFileType,
												connector_id: selectedAccountId ? Number(selectedAccountId) : null,
												parent_folder_id: parentFolderId.trim() || null,
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

			{/* Context section */}
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
										Google Drive Account <span className="text-destructive">*</span>
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
							)}

								<div className="space-y-2">
									<p className="text-xs font-medium text-muted-foreground">
										File Type <span className="text-destructive">*</span>
									</p>
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

								<div className="space-y-2">
									<p className="text-xs font-medium text-muted-foreground">
										Parent Folder ID (optional)
									</p>
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
				</>
			)}

			{/* Content preview */}
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 pt-3">
				{args.name != null && (
					<p className="text-sm font-medium text-foreground">{args.name}</p>
				)}
				{args.file_type && (
					<p className="text-xs text-muted-foreground mt-0.5">
						{FILE_TYPE_LABELS[args.file_type] ?? args.file_type}
					</p>
				)}
				{args.content != null && (
					<div
						className="mt-2 max-h-[7rem] overflow-hidden text-sm"
						style={{
							maskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
							WebkitMaskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
						}}
					>
						<PlateEditor
							markdown={String(args.content)}
							readOnly
							preset="readonly"
							editorVariant="none"
							className="h-auto [&_[data-slate-editor]]:!min-h-0 [&_[data-slate-editor]>*:first-child]:!mt-0"
						/>
					</div>
				)}
			</div>

			{/* Action buttons - only shown when pending */}
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
								Approve
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
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border border-amber-500/50 bg-muted/30">
			<div className="px-5 pt-5 pb-4">
				<div className="flex items-center gap-2">
					<AlertTriangleIcon className="size-4 text-amber-500 shrink-0" />
					<p className="text-sm font-semibold text-amber-600 dark:text-amber-400">
						Additional permissions required
					</p>
				</div>
			</div>
			<div className="mx-5 h-px bg-amber-500/30" />
			<div className="px-5 py-4 space-y-3">
				<p className="text-sm text-muted-foreground">{result.message}</p>
				<Button size="sm" className="rounded-lg" onClick={handleReauth} disabled={loading}>
					<RefreshCwIcon className={`size-4 ${loading ? "animate-spin" : ""}`} />
					Re-authenticate Google Drive
				</Button>
			</div>
		</div>
	);
}

function ErrorCard({ result }: { result: ErrorResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">Failed to create Google Drive file</p>
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
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30">
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

function SuccessCard({ result }: { result: SuccessResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-foreground">
					{result.message || "Google Drive file created successfully"}
				</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4 space-y-2 text-xs">
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
				<div className="my-4 max-w-lg rounded-2xl border bg-muted/30 px-5 py-4">
					<TextShimmerLoader text="Preparing Google Drive file..." size="sm" />
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

		if (isAuthErrorResult(result)) return <AuthErrorCard result={result} />;

		if (isInsufficientPermissionsResult(result))
			return <InsufficientPermissionsCard result={result} />;

		if (isErrorResult(result)) return <ErrorCard result={result} />;

		return <SuccessCard result={result as SuccessResult} />;
	},
});
