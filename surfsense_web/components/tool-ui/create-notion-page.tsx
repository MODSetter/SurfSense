"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { CheckIcon, FileTextIcon, Loader2Icon, XIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";

interface InterruptResult {
	__interrupt__: true;
	__decided__?: "approve" | "reject";
	action_requests: Array<{
		name: string;
		args: Record<string, unknown>;
		description?: string;
	}>;
	review_configs: Array<{
		action_name: string;
		allowed_decisions: Array<"approve" | "edit" | "reject">;
	}>;
}

interface SuccessResult {
	status: string;
	page_id: string;
	title: string;
	url: string;
}

type CreateNotionPageResult = InterruptResult | SuccessResult;

function isInterruptResult(result: unknown): result is InterruptResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"__interrupt__" in result &&
		(result as InterruptResult).__interrupt__ === true
	);
}

function ApprovalCard({
	args,
	interruptData,
	onDecision,
}: {
	args: Record<string, unknown>;
	interruptData: InterruptResult;
	onDecision: (decision: { type: "approve" | "reject"; message?: string }) => void;
}) {
	const [decided, setDecided] = useState<"approve" | "reject" | null>(
		interruptData.__decided__ ?? null
	);
	const reviewConfig = interruptData.review_configs[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];

	return (
		<div className="my-4 max-w-md overflow-hidden rounded-xl border border-border bg-card">
			<div className="flex items-center gap-3 border-b border-border px-4 py-3">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
					<FileTextIcon className="size-4 text-primary" />
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-sm font-medium">Create Notion Page</p>
					<p className="truncate text-xs text-muted-foreground">
						Requires your approval to proceed
					</p>
				</div>
			</div>

		<div className="space-y-2 px-4 py-3">
			{args.title != null && (
				<div>
					<p className="text-xs font-medium text-muted-foreground">Title</p>
					<p className="text-sm">{String(args.title)}</p>
				</div>
			)}
			{args.content != null && (
				<div>
					<p className="text-xs font-medium text-muted-foreground">Content</p>
					<p className="line-clamp-4 text-sm whitespace-pre-wrap">{String(args.content)}</p>
				</div>
			)}
		</div>

			<div className="flex items-center gap-2 border-t border-border px-4 py-3">
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
						{allowedDecisions.includes("approve") && (
							<Button
								size="sm"
								onClick={() => {
									setDecided("approve");
									onDecision({ type: "approve" });
								}}
							>
								<CheckIcon />
								Approve
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

function SuccessCard({ result }: { result: SuccessResult }) {
	return (
		<div className="my-4 max-w-md overflow-hidden rounded-xl border border-border bg-card">
			<div className="flex items-center gap-3 px-4 py-3">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-green-500/10">
					<CheckIcon className="size-4 text-green-500" />
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-sm font-medium">{result.title}</p>
					<p className="text-xs text-muted-foreground">Notion page created</p>
				</div>
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

		return <SuccessCard result={result as SuccessResult} />;
	},
});
