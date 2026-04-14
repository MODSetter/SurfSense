"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useSetAtom } from "jotai";
import { CornerDownLeftIcon, FileIcon, Pen } from "lucide-react";
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
import { isInterruptResult, useHitlDecision } from "@/lib/hitl";
import type { InterruptResult, HitlDecision } from "@/lib/hitl";

interface DropboxAccount {
	id: number;
	name: string;
	user_email?: string;
	auth_expired?: boolean;
}

interface SupportedType {
	value: string;
	label: string;
}

type DropboxCreateFileContext = {
	accounts?: DropboxAccount[];
	parent_folders?: Record<number, Array<{ folder_path: string; name: string }>>;
	supported_types?: SupportedType[];
	error?: string;
}

interface SuccessResult {
	status: "success";
	file_id: string;
	name: string;
	web_url?: string;
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

type CreateDropboxFileResult = InterruptResult<DropboxCreateFileContext> | SuccessResult | ErrorResult | AuthErrorResult;

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

function ApprovalCard({
	args,
	interruptData,
	onDecision,
}: {
	args: { name: string; file_type?: string; content?: string };
	interruptData: InterruptResult<DropboxCreateFileContext>;
	onDecision: (decision: HitlDecision) => void;
}) {
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);
	const [isPanelOpen, setIsPanelOpen] = useState(false);
	const openHitlEditPanel = useSetAtom(openHitlEditPanelAtom);
	const [pendingEdits, setPendingEdits] = useState<{ name: string; content: string } | null>(null);

	const accounts = interruptData.context?.accounts ?? [];
	const validAccounts = accounts.filter((a) => !a.auth_expired);
	const expiredAccounts = accounts.filter((a) => a.auth_expired);
	const supportedTypes = interruptData.context?.supported_types ?? [
		{ value: "paper", label: "Dropbox Paper (.paper)" },
		{ value: "docx", label: "Word Document (.docx)" },
	];

	const defaultAccountId = useMemo(() => {
		if (validAccounts.length === 1) return String(validAccounts[0].id);
		return "";
	}, [validAccounts]);

	const [selectedAccountId, setSelectedAccountId] = useState<string>(defaultAccountId);
	const [parentFolderPath, setParentFolderPath] = useState<string>("__root__");
	const [selectedFileType, setSelectedFileType] = useState<string>(args.file_type ?? "paper");

	const parentFolders = interruptData.context?.parent_folders ?? {};
	const availableParentFolders = useMemo(() => {
		if (!selectedAccountId) return [];
		return parentFolders[Number(selectedAccountId)] ?? [];
	}, [selectedAccountId, parentFolders]);

	const handleAccountChange = useCallback((value: string) => {
		setSelectedAccountId(value);
		setParentFolderPath("__root__");
	}, []);

	const isNameValid = useMemo(() => {
		const name = pendingEdits?.name ?? args.name;
		return name && typeof name === "string" && name.trim().length > 0;
	}, [pendingEdits?.name, args.name]);

	const canApprove = !!selectedAccountId && isNameValid;
	const reviewConfig = interruptData.review_configs?.[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	const fileTypeLabel =
		supportedTypes.find((t) => t.value === selectedFileType)?.label ?? selectedFileType;

	const handleApprove = useCallback(() => {
		if (phase !== "pending" || isPanelOpen || !canApprove) return;
		if (!allowedDecisions.includes("approve")) return;
		const isEdited = pendingEdits !== null || selectedFileType !== (args.file_type ?? "paper");
		setProcessing();
		onDecision({
			type: isEdited ? "edit" : "approve",
			edited_action: {
				name: interruptData.action_requests[0].name,
				args: {
					...args,
					...(pendingEdits && { name: pendingEdits.name, content: pendingEdits.content }),
					file_type: selectedFileType,
					connector_id: selectedAccountId ? Number(selectedAccountId) : null,
					parent_folder_path: parentFolderPath === "__root__" ? null : parentFolderPath,
				},
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
		args,
		selectedAccountId,
		parentFolderPath,
		pendingEdits,
		selectedFileType,
	]);

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
							? "Dropbox File Rejected"
							: phase === "processing" || phase === "complete"
								? "Dropbox File Approved"
								: "Create Dropbox File"}
					</p>
					{phase === "processing" ? (
						<TextShimmerLoader
							text={pendingEdits ? "Creating file with your changes" : "Creating file"}
							size="sm"
						/>
					) : phase === "complete" ? (
						<p className="text-xs text-muted-foreground mt-0.5">
							{pendingEdits ? "File created with your changes" : "File created"}
						</p>
					) : phase === "rejected" ? (
						<p className="text-xs text-muted-foreground mt-0.5">File creation was cancelled</p>
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
								title: pendingEdits?.name ?? args.name ?? "",
								content: pendingEdits?.content ?? args.content ?? "",
								toolName: fileTypeLabel,
								onSave: (newName, newContent) => {
									setIsPanelOpen(false);
									setPendingEdits({ name: newName, content: newContent });
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
											Dropbox Account <span className="text-destructive">*</span>
										</p>
										<Select value={selectedAccountId} onValueChange={handleAccountChange}>
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
									<p className="text-xs font-medium text-muted-foreground">File Type</p>
									<Select value={selectedFileType} onValueChange={setSelectedFileType}>
										<SelectTrigger className="w-full">
											<SelectValue />
										</SelectTrigger>
										<SelectContent>
											{supportedTypes.map((t) => (
												<SelectItem key={t.value} value={t.value}>
													{t.label}
												</SelectItem>
											))}
										</SelectContent>
									</Select>
								</div>

								{selectedAccountId && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">Parent Folder</p>
										<Select value={parentFolderPath} onValueChange={setParentFolderPath}>
											<SelectTrigger className="w-full">
												<SelectValue placeholder="Dropbox Root" />
											</SelectTrigger>
											<SelectContent>
												<SelectItem value="__root__">Dropbox Root</SelectItem>
												{availableParentFolders.map((folder) => (
													<SelectItem key={folder.folder_path} value={folder.folder_path}>
														{folder.name}
													</SelectItem>
												))}
											</SelectContent>
										</Select>
										{availableParentFolders.length === 0 && (
											<p className="text-xs text-muted-foreground">
												No folders found. File will be created at Dropbox root.
											</p>
										)}
									</div>
								)}
							</>
						)}
					</div>
				</>
			)}

			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 pt-3">
				{(pendingEdits?.name ?? args.name) != null && (
					<p className="text-sm font-medium text-foreground">
						{String(pendingEdits?.name ?? args.name)}
					</p>
				)}
				{(pendingEdits?.content ?? args.content) != null && (
					<div
						className="mt-2 max-h-[7rem] overflow-hidden text-sm"
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
								Approve <CornerDownLeftIcon className="size-3 opacity-60" />
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
				<p className="text-sm font-semibold text-destructive">Failed to create Dropbox file</p>
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
					{result.message || "Dropbox file created successfully"}
				</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4 space-y-2 text-xs">
				<div className="flex items-center gap-1.5">
					<FileIcon className="size-3.5 text-muted-foreground" />
					<span className="font-medium">{result.name}</span>
				</div>
				{result.web_url && (
					<div>
						<a
							href={result.web_url}
							target="_blank"
							rel="noopener noreferrer"
							className="text-primary hover:underline"
						>
							Open in Dropbox
						</a>
					</div>
				)}
			</div>
		</div>
	);
}

export const CreateDropboxFileToolUI = ({
	args,
	result,
}: ToolCallMessagePartProps<
	{ name: string; file_type?: string; content?: string },
	CreateDropboxFileResult
>) => {
	const { dispatch } = useHitlDecision();
	if (!result) return null;
	if (isInterruptResult(result)) {
		return (
			<ApprovalCard
				args={args}
				interruptData={result as InterruptResult<DropboxCreateFileContext>}
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
	if (isErrorResult(result)) return <ErrorCard result={result} />;
	return <SuccessCard result={result as SuccessResult} />;
};
