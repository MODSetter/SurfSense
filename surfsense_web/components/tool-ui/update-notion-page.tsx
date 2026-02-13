"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
	AlertTriangleIcon,
	CheckIcon,
	InfoIcon,
	Loader2Icon,
	MaximizeIcon,
	MinimizeIcon,
	PencilIcon,
	XIcon,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface InterruptResult {
	__interrupt__: true;
	__decided__?: "approve" | "reject" | "edit";
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
		account?: {
			id: number;
			name: string;
			workspace_id: string | null;
			workspace_name: string;
			workspace_icon: string;
		};
		page_id?: string;
		current_title?: string;
		document_id?: number;
		indexed_at?: string;
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

interface InfoResult {
	status: "not_found";
	message: string;
}

type UpdateNotionPageResult = InterruptResult | SuccessResult | ErrorResult | InfoResult;

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

function isInfoResult(result: unknown): result is InfoResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as InfoResult).status === "not_found"
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
	const [decided, setDecided] = useState<"approve" | "reject" | "edit" | null>(
		interruptData.__decided__ ?? null
	);
	const [isEditing, setIsEditing] = useState(false);
	const [isFullScreen, setIsFullScreen] = useState(false);
	const [editedArgs, setEditedArgs] = useState<Record<string, unknown>>(args);

	const account = interruptData.context?.account;
	const currentTitle = interruptData.context?.current_title;

	// Title is not editable, so it's always valid
	const isTitleValid = true;

	const reviewConfig = interruptData.review_configs[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	return (
		<div
			className={`my-4 ${isFullScreen ? "fixed inset-0 z-50 m-0 flex flex-col bg-background" : "max-w-full"} overflow-hidden rounded-xl transition-all duration-300 ${
				decided
					? "border border-border bg-card shadow-sm"
					: "border-2 border-foreground/20 bg-muted/30 dark:bg-muted/10 shadow-lg animate-pulse-subtle"
			}`}
		>
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
					<p className={`text-sm font-medium ${decided ? "text-foreground" : "text-foreground"}`}>
						Update Notion Page
					</p>
					<p
						className={`truncate text-xs ${
							decided ? "text-muted-foreground" : "text-muted-foreground"
						}`}
					>
						{isEditing ? "You can edit the arguments below" : "Requires your approval to proceed"}
					</p>
				</div>
				{isEditing && (
					<Button
						size="sm"
						variant="ghost"
						onClick={() => setIsFullScreen(!isFullScreen)}
						className="shrink-0"
					>
						{isFullScreen ? <MinimizeIcon className="size-4" /> : <MaximizeIcon className="size-4" />}
					</Button>
				)}
			</div>

			{/* Context section - READ ONLY account and page info */}
			{!decided && interruptData.context && (
				<div className="border-b border-border px-4 py-3 bg-muted/30 space-y-3">
					{interruptData.context.error ? (
						<p className="text-sm text-destructive">{interruptData.context.error}</p>
					) : (
						<>
							{account && (
								<div className="space-y-2">
									<div className="text-xs font-medium text-muted-foreground">Notion Account</div>
									<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm">
										{account.workspace_icon} {account.workspace_name}
									</div>
								</div>
							)}

							{currentTitle && (
								<div className="space-y-2">
									<div className="text-xs font-medium text-muted-foreground">Current Page</div>
									<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm">
										📄 {currentTitle}
									</div>
								</div>
							)}
						</>
					)}
				</div>
			)}

			{/* Display mode - show proposed changes as read-only */}
			{!isEditing && (
				<div
					className={`space-y-2 px-4 py-3 bg-card ${isFullScreen ? "flex-1 overflow-y-auto" : ""}`}
				>
					{args.content != null && (
						<div>
							<p className="text-xs font-medium text-muted-foreground">New Content</p>
							<p className="line-clamp-4 text-sm whitespace-pre-wrap text-foreground">
								{String(args.content)}
							</p>
						</div>
					)}
					{args.content == null && (
						<p className="text-sm text-muted-foreground italic">No content update specified</p>
					)}
				</div>
			)}

			{/* Edit mode - show editable form fields */}
			{isEditing && !decided && (
				<div
					className={`px-4 py-3 bg-card ${isFullScreen ? "flex-1 flex flex-col overflow-hidden" : ""}`}
				>
					<label
						htmlFor="notion-content"
						className="text-xs font-medium text-muted-foreground mb-1.5 block"
					>
						New Content
					</label>
					<Textarea
						id="notion-content"
						value={String(editedArgs.content ?? "")}
						onChange={(e) => setEditedArgs({ ...editedArgs, content: e.target.value || null })}
						placeholder="Enter content to append to the page"
						rows={isFullScreen ? undefined : 12}
						className={`resize-none ${isFullScreen ? "flex-1 min-h-0" : ""}`}
					/>
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
								setDecided("edit");
								setIsEditing(false);
								setIsFullScreen(false);
								onDecision({
									type: "edit",
									edited_action: {
										name: interruptData.action_requests[0].name,
										args: {
											page_id: args.page_id,
											content: editedArgs.content,
											connector_id: account?.id,
										},
									},
								});
							}}
						>
							<CheckIcon />
							Approve with Changes
						</Button>
						<Button
							size="sm"
							variant="outline"
							onClick={() => {
								setIsEditing(false);
								setIsFullScreen(false);
								setEditedArgs(args); // Reset to original args
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
									setDecided("approve");
									onDecision({
										type: "approve",
										edited_action: {
											name: interruptData.action_requests[0].name,
											args: {
												page_id: args.page_id,
												content: args.content,
												connector_id: account?.id,
											},
										},
									});
								}}
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

function ErrorCard({ result }: { result: ErrorResult }) {
	return (
		<div className="my-4 max-w-md overflow-hidden rounded-xl border border-destructive/50 bg-card">
			<div className="flex items-center gap-3 border-b border-destructive/50 px-4 py-3">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-destructive/10">
					<XIcon className="size-4 text-destructive" />
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-sm font-medium text-destructive">Failed to update Notion page</p>
				</div>
			</div>
			<div className="px-4 py-3">
				<p className="text-sm text-muted-foreground">{result.message}</p>
			</div>
		</div>
	);
}

function InfoCard({ result }: { result: InfoResult }) {
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
						{result.message || "Notion page updated successfully"}
					</p>
				</div>
			</div>

			{/* Show details to verify the update */}
			<div className="space-y-2 px-4 py-3 text-xs">
				<div>
					<span className="font-medium text-muted-foreground">Page ID: </span>
					<span className="font-mono">{result.page_id}</span>
				</div>
				<div>
					<span className="font-medium text-muted-foreground">Title: </span>
					<span>{result.title}</span>
				</div>
				{result.url && (
					<div>
						<span className="font-medium text-muted-foreground">URL: </span>
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
				{result.content_length != null && (
					<div>
						<span className="font-medium text-muted-foreground">Content: </span>
						<span>{result.content_length} characters</span>
					</div>
				)}
				{result.content_preview && (
					<div>
						<span className="font-medium text-muted-foreground">Preview: </span>
						<span className="text-muted-foreground italic">{result.content_preview}</span>
					</div>
				)}
			</div>
		</div>
	);
}

export const UpdateNotionPageToolUI = makeAssistantToolUI<
	{ page_id: string; content: string },
	UpdateNotionPageResult
>({
	toolName: "update_notion_page",
	render: function UpdateNotionPageUI({ args, result, status }) {
		if (status.type === "running") {
			return (
				<div className="my-4 flex max-w-md items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
					<Loader2Icon className="size-4 animate-spin text-muted-foreground" />
					<p className="text-sm text-muted-foreground">Updating Notion page...</p>
				</div>
			);
		}

		if (!result) {
			return null;
		}

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

		if (
			typeof result === "object" &&
			result !== null &&
			"status" in result &&
			(result as { status: string }).status === "rejected"
		) {
			return null;
		}

		if (isInfoResult(result)) {
			return <InfoCard result={result} />;
		}

		if (isErrorResult(result)) {
			return <ErrorCard result={result} />;
		}

		return <SuccessCard result={result as SuccessResult} />;
	},
});
