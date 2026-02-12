"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
	AlertTriangleIcon,
	CheckIcon,
	Loader2Icon,
	Maximize2Icon,
	PencilIcon,
	XIcon,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
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
		current_content?: string;
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
	message?: string;
}

interface ErrorResult {
	status: "error";
	message: string;
}

type UpdateNotionPageResult = InterruptResult | SuccessResult | ErrorResult;

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

function PageContextDisplay({
	account,
	currentTitle,
	currentContent,
}: {
	account?: {
		id: number;
		name: string;
		workspace_id: string | null;
		workspace_name: string;
		workspace_icon: string;
	};
	currentTitle?: string;
	currentContent?: string;
}) {
	return (
		<>
			{account && (
				<div className="space-y-2">
					<div className="text-xs font-medium text-muted-foreground">Notion Account</div>
					<div className="text-sm text-foreground p-2 bg-card rounded border border-border">
						{account.workspace_name}
					</div>
				</div>
			)}

			{currentTitle && (
				<div className="space-y-2">
					<div className="text-xs font-medium text-muted-foreground">Current Page Title</div>
					<div className="text-sm text-foreground p-2 bg-card rounded border border-border">
						{currentTitle}
					</div>
				</div>
			)}

			{currentContent && (
				<div className="space-y-2">
					<div className="text-xs font-medium text-muted-foreground">
						Current Content (first 200 chars)
					</div>
					<div className="text-sm text-muted-foreground p-2 bg-card rounded border border-border font-mono text-xs">
						{currentContent.slice(0, 200)}
						{currentContent.length > 200 && "..."}
					</div>
				</div>
			)}
		</>
	);
}

function EditFormFields({
	editedArgs,
	setEditedArgs,
	isTitleValid,
	idPrefix = "",
	rows = 8,
}: {
	editedArgs: Record<string, unknown>;
	setEditedArgs: (args: Record<string, unknown>) => void;
	isTitleValid: boolean;
	idPrefix?: string;
	rows?: number;
}) {
	return (
		<>
			<div>
				<label
					htmlFor={`${idPrefix}notion-title`}
					className="text-xs font-medium text-muted-foreground mb-1.5 block"
				>
					Title <span className="text-destructive">*</span>
				</label>
				<Input
					id={`${idPrefix}notion-title`}
					value={String(editedArgs.title ?? "")}
					onChange={(e) => setEditedArgs({ ...editedArgs, title: e.target.value })}
					placeholder="Enter page title"
					className={!isTitleValid ? "border-destructive" : ""}
				/>
				{!isTitleValid && (
					<p className="text-xs text-destructive mt-1">Title is required and cannot be empty</p>
				)}
			</div>
			<div>
				<label
					htmlFor={`${idPrefix}notion-content`}
					className="text-xs font-medium text-muted-foreground mb-1.5 block"
				>
					Content (optional)
				</label>
				<Textarea
					id={`${idPrefix}notion-content`}
					value={String(editedArgs.content ?? "")}
					onChange={(e) => setEditedArgs({ ...editedArgs, content: e.target.value })}
					placeholder="Enter page content"
					rows={rows}
					className="resize-none font-mono text-xs"
				/>
			</div>
		</>
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

	const account = interruptData.context?.account;
	const currentTitle = interruptData.context?.current_title;
	const currentContent = interruptData.context?.current_content;

	const [editedArgs, setEditedArgs] = useState<Record<string, unknown>>({
		...args,
		title: args.title || currentTitle || "",
		content: args.content || currentContent || "",
	});

	const isTitleValid = useMemo((): boolean => {
		const title = isEditing ? editedArgs.title : args.title || currentTitle;
		return Boolean(title && typeof title === "string" && title.trim().length > 0);
	}, [isEditing, editedArgs.title, args.title, currentTitle]);

	const reviewConfig = interruptData.review_configs[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	return (
		<div
			className={`my-4 max-w-full overflow-hidden rounded-xl transition-all duration-300 ${
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
				{canEdit && !decided && !isEditing && (
					<>
						<Button size="sm" variant="ghost" onClick={() => setIsFullScreen(true)}>
							<Maximize2Icon className="size-4" />
						</Button>
						<Button size="sm" variant="ghost" onClick={() => setIsEditing(true)}>
							<PencilIcon className="size-4" />
							Edit
						</Button>
					</>
				)}
			</div>

			{!decided && interruptData.context && (
				<div className="border-b border-border px-4 py-3 bg-muted/30 space-y-3">
					{interruptData.context.error ? (
						<p className="text-sm text-destructive">{interruptData.context.error}</p>
					) : (
						<PageContextDisplay
							account={account}
							currentTitle={currentTitle}
							currentContent={currentContent}
						/>
					)}
				</div>
			)}

			{!isEditing && (
				<div className="space-y-2 px-4 py-3 bg-card">
					{args.title != null && (
						<div>
							<div className="text-xs font-medium text-muted-foreground mb-1.5 block">
								New Title
							</div>
							<p className="text-sm text-foreground">{String(args.title)}</p>
						</div>
					)}
					{args.content != null && (
						<div>
							<div className="text-xs font-medium text-muted-foreground mb-1.5 block">
								New Content
							</div>
							<p className="text-sm text-foreground whitespace-pre-wrap font-mono text-xs">
								{String(args.content).slice(0, 300)}
								{String(args.content).length > 300 && "..."}
							</p>
						</div>
					)}
				</div>
			)}

			{isEditing && !decided && (
				<div className="space-y-3 px-4 py-3 bg-card">
					<EditFormFields
						editedArgs={editedArgs}
						setEditedArgs={setEditedArgs}
						isTitleValid={isTitleValid}
						rows={8}
					/>
				</div>
			)}

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
								onDecision({
									type: "edit",
									edited_action: {
										name: interruptData.action_requests[0].name,
										args: editedArgs,
									},
								});
							}}
							disabled={!isTitleValid}
						>
							<CheckIcon />
							Approve with Changes
						</Button>
						<Button
							size="sm"
							variant="outline"
							onClick={() => {
								setIsEditing(false);
								setEditedArgs({
									...args,
									title: args.title || currentTitle || "",
									content: args.content || currentContent || "",
								});
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
											args: args,
										},
									});
								}}
								disabled={!isTitleValid}
							>
								<CheckIcon />
								Approve
							</Button>
						)}
						{allowedDecisions.includes("reject") && (
							<Button
								size="sm"
								variant="destructive"
								onClick={() => {
									setDecided("reject");
									onDecision({ type: "reject" });
								}}
							>
								<XIcon />
								Reject
							</Button>
						)}
					</>
				)}
			</div>

			<Dialog open={isFullScreen} onOpenChange={setIsFullScreen}>
				<DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
					<DialogHeader>
						<DialogTitle>Update Notion Page</DialogTitle>
					</DialogHeader>

					<PageContextDisplay
						account={account}
						currentTitle={currentTitle}
						currentContent={undefined}
					/>

					<div className="space-y-4">
						<EditFormFields
							editedArgs={editedArgs}
							setEditedArgs={setEditedArgs}
							isTitleValid={isTitleValid}
							idPrefix="fullscreen-"
							rows={20}
						/>
					</div>

					<div className="flex items-center gap-2 justify-end pt-4 border-t">
						<Button
							size="sm"
							onClick={() => {
								setDecided("edit");
								setIsFullScreen(false);
								onDecision({
									type: "edit",
									edited_action: {
										name: interruptData.action_requests[0].name,
										args: editedArgs,
									},
								});
							}}
							disabled={!isTitleValid}
						>
							<CheckIcon />
							Approve with Changes
						</Button>
						<Button
							size="sm"
							variant="outline"
							onClick={() => {
								setIsFullScreen(false);
								setEditedArgs({
									...args,
									title: args.title || currentTitle || "",
									content: args.content || currentContent || "",
								});
							}}
						>
							Cancel
						</Button>
					</div>
				</DialogContent>
			</Dialog>
		</div>
	);
}

function LoadingCard() {
	return (
		<div className="my-4 flex items-center gap-3 rounded-xl border-2 border-blue-200 bg-blue-50 px-4 py-3 dark:border-blue-900 dark:bg-blue-950">
			<Loader2Icon className="size-5 animate-spin text-blue-600 dark:text-blue-400" />
			<p className="text-sm text-blue-900 dark:text-blue-100">Updating Notion page...</p>
		</div>
	);
}

function SuccessCard({ result }: { result: SuccessResult }) {
	return (
		<div className="my-4 rounded-xl border border-green-200 bg-green-50 p-4 dark:border-green-900 dark:bg-green-950">
			<div className="flex items-start gap-3">
				<CheckIcon className="size-5 shrink-0 text-green-600 dark:text-green-400" />
				<div className="flex-1 space-y-2">
					<p className="text-sm font-medium text-green-900 dark:text-green-100">
						Updated Notion page '{result.title}'
					</p>
					{result.url && (
						<a
							href={result.url}
							target="_blank"
							rel="noopener noreferrer"
							className="inline-block text-sm text-green-700 underline hover:text-green-800 dark:text-green-300 dark:hover:text-green-200"
						>
							Open in Notion →
						</a>
					)}
				</div>
			</div>
		</div>
	);
}

function ErrorCard({ result }: { result: ErrorResult }) {
	return (
		<div className="my-4 rounded-xl border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950">
			<div className="flex items-start gap-3">
				<XIcon className="size-5 shrink-0 text-red-600 dark:text-red-400" />
				<div className="flex-1">
					<p className="text-sm font-medium text-red-900 dark:text-red-100">
						Failed to update page
					</p>
					<p className="mt-1 text-sm text-red-700 dark:text-red-300">{result.message}</p>
				</div>
			</div>
		</div>
	);
}

export const UpdateNotionPageToolUI = makeAssistantToolUI<
	{ page_id: string; title?: string | null; content?: string | null },
	UpdateNotionPageResult
>({
	toolName: "update_notion_page",
	render: function UpdateNotionPageUI({ result, addResult, status }) {
		if (status.type === "running") {
			return <LoadingCard />;
		}

		if (isInterruptResult(result)) {
			const args = result.action_requests[0]?.args || {};

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

		if (isErrorResult(result)) {
			return <ErrorCard result={result} />;
		}

		if (typeof result === "object" && result !== null && "status" in result) {
			const successResult = result as SuccessResult;
			if (successResult.status === "success") {
				return <SuccessCard result={successResult} />;
			}
		}

		return null;
	},
});
