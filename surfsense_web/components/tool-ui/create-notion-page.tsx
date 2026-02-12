"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { AlertTriangleIcon, CheckIcon, Loader2Icon, PencilIcon, XIcon } from "lucide-react";
import { useMemo, useState } from "react";
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
		accounts?: Array<{
			id: number;
			name: string;
			workspace_id: string | null;
			workspace_name: string;
			workspace_icon: string;
		}>;
		parent_pages?: Record<
			number,
			Array<{
				page_id: string;
				title: string;
				document_id: number;
			}>
		>;
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

type CreateNotionPageResult = InterruptResult | SuccessResult | ErrorResult;

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
	const [editedArgs, setEditedArgs] = useState<Record<string, unknown>>(args);

	const accounts = interruptData.context?.accounts ?? [];
	const parentPages = interruptData.context?.parent_pages ?? {};

	const defaultAccountId = useMemo(() => {
		if (args.connector_id) return String(args.connector_id);
		if (accounts.length === 1) return String(accounts[0].id);
		return "";
	}, [args.connector_id, accounts]);

	const [selectedAccountId, setSelectedAccountId] = useState<string>(defaultAccountId);
	const [selectedParentPageId, setSelectedParentPageId] = useState<string>(
		args.parent_page_id ? String(args.parent_page_id) : "__none__"
	);

	const availableParentPages = useMemo(() => {
		if (!selectedAccountId) return [];
		return parentPages[Number(selectedAccountId)] ?? [];
	}, [selectedAccountId, parentPages]);

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
						Create Notion Page
					</p>
					<p
						className={`truncate text-xs ${
							decided ? "text-muted-foreground" : "text-muted-foreground"
						}`}
					>
						{isEditing ? "You can edit the arguments below" : "Requires your approval to proceed"}
					</p>
				</div>
			</div>

			{/* Context section - account and parent page selection */}
			{!decided && interruptData.context && (
				<div className="border-b border-border px-4 py-3 bg-muted/30 space-y-3">
					{interruptData.message && (
						<p className="text-sm text-foreground">{interruptData.message}</p>
					)}

					{interruptData.context.error ? (
						<p className="text-sm text-destructive">{interruptData.context.error}</p>
					) : (
						<>
							{accounts.length > 0 && (
								<div className="space-y-2">
									<label className="text-xs font-medium text-muted-foreground">
										Notion Account <span className="text-destructive">*</span>
									</label>
									<Select
										value={selectedAccountId}
										onValueChange={(value) => {
											setSelectedAccountId(value);
											setSelectedParentPageId("__none__");
										}}
									>
										<SelectTrigger className="w-full">
											<SelectValue placeholder="Select an account" />
										</SelectTrigger>
										<SelectContent>
											{accounts.map((account) => (
												<SelectItem key={account.id} value={String(account.id)}>
												{account.workspace_name}
												</SelectItem>
											))}
										</SelectContent>
									</Select>
								</div>
							)}

							{selectedAccountId && (
								<div className="space-y-2">
									<label className="text-xs font-medium text-muted-foreground">
										Parent Page (optional)
									</label>
									<Select value={selectedParentPageId} onValueChange={setSelectedParentPageId}>
										<SelectTrigger className="w-full">
											<SelectValue placeholder="None (create at root level)" />
										</SelectTrigger>
										<SelectContent>
											<SelectItem value="__none__">None (create at root level)</SelectItem>
											{availableParentPages.map((page) => (
												<SelectItem key={page.page_id} value={page.page_id}>
													📄 {page.title}
												</SelectItem>
											))}
										</SelectContent>
									</Select>
									{availableParentPages.length === 0 && selectedAccountId && (
										<p className="text-xs text-muted-foreground">
											No pages available. Page will be created at root level.
										</p>
									)}
								</div>
							)}
						</>
					)}
				</div>
			)}

			{/* Display mode - show args as read-only */}
			{!isEditing && (
				<div className="space-y-2 px-4 py-3 bg-card">
					{args.title != null && (
						<div>
							<p className="text-xs font-medium text-muted-foreground">Title</p>
							<p className="text-sm text-foreground">{String(args.title)}</p>
						</div>
					)}
					{args.content != null && (
						<div>
							<p className="text-xs font-medium text-muted-foreground">Content</p>
							<p className="line-clamp-4 text-sm whitespace-pre-wrap text-foreground">
								{String(args.content)}
							</p>
						</div>
					)}
				</div>
			)}

			{/* Edit mode - show editable form fields */}
			{isEditing && (
				<div className="space-y-3 px-4 py-3 bg-card">
					<div>
						<label
							htmlFor="notion-title"
							className="text-xs font-medium text-muted-foreground mb-1.5 block"
						>
							Title
						</label>
						<Input
							id="notion-title"
							value={String(editedArgs.title ?? "")}
							onChange={(e) => setEditedArgs({ ...editedArgs, title: e.target.value })}
							placeholder="Enter page title"
						/>
					</div>
					<div>
						<label
							htmlFor="notion-content"
							className="text-xs font-medium text-muted-foreground mb-1.5 block"
						>
							Content
						</label>
						<Textarea
							id="notion-content"
							value={String(editedArgs.content ?? "")}
							onChange={(e) => setEditedArgs({ ...editedArgs, content: e.target.value })}
							placeholder="Enter page content"
							rows={6}
							className="resize-none"
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
								setDecided("edit");
								onDecision({
									type: "edit",
									edited_action: {
										name: interruptData.action_requests[0].name,
										args: {
											...editedArgs,
											connector_id: selectedAccountId ? Number(selectedAccountId) : null,
											parent_page_id: selectedParentPageId === "__none__" ? null : selectedParentPageId,
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
												...args,
												connector_id: selectedAccountId ? Number(selectedAccountId) : null,
												parent_page_id: selectedParentPageId === "__none__" ? null : selectedParentPageId,
											},
										},
									});
								}}
								disabled={!selectedAccountId}
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
					<p className="text-sm font-medium text-destructive">Failed to create Notion page</p>
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
					<p className=" text-[.8rem] text-muted-foreground">
						{result.message || "Notion page created successfully"}
					</p>
				</div>
			</div>

			{/* Show details to verify the arguments were used */}
			<div className="space-y-2 px-4 py-3 text-xs">
				<div>
					<span className="font-medium text-muted-foreground">Page ID: </span>
					<span className="font-mono">{result.page_id}</span>
				</div>
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

export const CreateNotionPageToolUI = makeAssistantToolUI<
	{ title: string; content: string },
	CreateNotionPageResult
>({
	toolName: "create_notion_page",
	render: function CreateNotionPageUI({ args, result, status }) {
		if (status.type === "running") {
			return (
				<div className="my-4 flex max-w-md items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
					<Loader2Icon className="size-4 animate-spin text-muted-foreground" />
					<p className="text-sm text-muted-foreground">Preparing Notion page...</p>
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

		if (isErrorResult(result)) {
			return <ErrorCard result={result} />;
		}

		return <SuccessCard result={result as SuccessResult} />;
	},
});
