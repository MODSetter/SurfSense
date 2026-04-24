"use client";

import type { ToolCallMessagePartComponent } from "@assistant-ui/react";
import { CornerDownLeftIcon, Pencil } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useHitlPhase } from "@/hooks/use-hitl-phase";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";
import type { HitlDecision, InterruptResult } from "@/lib/hitl";
import { isInterruptResult, useHitlDecision } from "@/lib/hitl";

function ParamEditor({
	params,
	onChange,
	disabled,
}: {
	params: Record<string, unknown>;
	onChange: (updated: Record<string, unknown>) => void;
	disabled: boolean;
}) {
	const entries = Object.entries(params);
	if (entries.length === 0) return null;

	return (
		<div className="space-y-2">
			{entries.map(([key, value]) => {
				const strValue = value == null ? "" : String(value);
				const isLong = strValue.length > 120;
				const fieldId = `hitl-param-${key}`;

				return (
					<div key={key} className="space-y-1">
						<label htmlFor={fieldId} className="text-xs font-medium text-muted-foreground">
							{key}
						</label>
						{isLong ? (
							<Textarea
								id={fieldId}
								value={strValue}
								disabled={disabled}
								rows={3}
								onChange={(e) => onChange({ ...params, [key]: e.target.value })}
								className="text-xs"
							/>
						) : (
							<Input
								id={fieldId}
								value={strValue}
								disabled={disabled}
								onChange={(e) => onChange({ ...params, [key]: e.target.value })}
								className="text-xs"
							/>
						)}
					</div>
				);
			})}
		</div>
	);
}

function GenericApprovalCard({
	toolName,
	args,
	interruptData,
	onDecision,
}: {
	toolName: string;
	args: Record<string, unknown>;
	interruptData: InterruptResult;
	onDecision: (decision: HitlDecision) => void;
}) {
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);
	const [editedParams, setEditedParams] = useState<Record<string, unknown>>(args);
	const [isEditing, setIsEditing] = useState(false);

	const displayName = toolName.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

	const mcpServer = interruptData.context?.mcp_server as string | undefined;
	const toolDescription = interruptData.context?.tool_description as string | undefined;
	const mcpConnectorId = interruptData.context?.mcp_connector_id as number | undefined;
	const isMCPTool = mcpConnectorId != null;

	const reviewConfig = interruptData.review_configs?.[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	const hasChanged = useMemo(() => {
		return JSON.stringify(editedParams) !== JSON.stringify(args);
	}, [editedParams, args]);

	const handleApprove = useCallback(() => {
		if (phase !== "pending") return;
		const isEdited = isEditing && hasChanged;
		setProcessing();
		onDecision({
			type: isEdited ? "edit" : "approve",
			edited_action: isEdited
				? { name: interruptData.action_requests[0]?.name ?? toolName, args: editedParams }
				: undefined,
		});
	}, [
		phase,
		setProcessing,
		isEditing,
		hasChanged,
		onDecision,
		interruptData,
		toolName,
		editedParams,
	]);

	const handleAlwaysAllow = useCallback(() => {
		if (phase !== "pending" || !isMCPTool) return;
		setProcessing();
		onDecision({ type: "approve" });
		connectorsApiService.trustMCPTool(mcpConnectorId, toolName).catch(() => {
			toast.error("Failed to save 'Always Allow' preference. The tool will still require approval next time.");
		});
	}, [phase, setProcessing, onDecision, isMCPTool, mcpConnectorId, toolName]);

	useEffect(() => {
		const handler = (e: KeyboardEvent) => {
			if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey && phase === "pending") {
				handleApprove();
			}
		};
		window.addEventListener("keydown", handler);
		return () => window.removeEventListener("keydown", handler);
	}, [handleApprove, phase]);

	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 transition-[box-shadow] duration-300">
			{/* Header */}
			<div className="flex items-start justify-between px-5 pt-5 pb-4 select-none">
				<div>
					<p className="text-sm font-semibold text-foreground">
						{phase === "rejected"
							? `${displayName} — Rejected`
							: phase === "processing" || phase === "complete"
								? `${displayName} — Approved`
								: displayName}
					</p>
					{phase === "processing" ? (
						<TextShimmerLoader text="Executing..." size="sm" />
					) : phase === "complete" ? (
						<p className="text-xs text-muted-foreground mt-0.5">Action completed</p>
					) : phase === "rejected" ? (
						<p className="text-xs text-muted-foreground mt-0.5">Action was cancelled</p>
					) : (
						<p className="text-xs text-muted-foreground mt-0.5">
							Requires your approval to proceed
						</p>
					)}
					{mcpServer && (
						<p className="text-[10px] text-muted-foreground/70 mt-1">
							via <span className="font-medium">{mcpServer}</span>
						</p>
					)}
				</div>
				{phase === "pending" && canEdit && !isEditing && (
					<Button
						size="sm"
						variant="ghost"
						className="rounded-lg text-muted-foreground -mt-1 -mr-2"
						onClick={() => setIsEditing(true)}
					>
						<Pencil className="size-3.5" />
						Edit
					</Button>
				)}
			</div>

			{/* Description */}
			{toolDescription && phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-3">
						<p className="text-xs text-muted-foreground">{toolDescription}</p>
					</div>
				</>
			)}

			{/* Parameters */}
			{Object.keys(args).length > 0 && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 space-y-2">
						<p className="text-xs font-medium text-muted-foreground">Parameters</p>
						{phase === "pending" && isEditing ? (
							<ParamEditor
								params={editedParams}
								onChange={setEditedParams}
								disabled={phase !== "pending"}
							/>
						) : (
							<pre className="text-xs text-foreground/80 whitespace-pre-wrap break-all bg-muted/50 rounded-lg p-3">
								{JSON.stringify(args, null, 2)}
							</pre>
						)}
					</div>
				</>
			)}

			{/* Action buttons */}
			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 flex items-center gap-2 select-none">
						{allowedDecisions.includes("approve") && (
							<Button size="sm" className="rounded-lg gap-1.5" onClick={handleApprove}>
								{isEditing && hasChanged ? "Approve with edits" : "Approve"}
								<CornerDownLeftIcon className="size-3 opacity-60" />
							</Button>
						)}
						{isMCPTool && (
							<Button size="sm" className="rounded-lg" onClick={handleAlwaysAllow}>
								Always Allow
							</Button>
						)}
						{allowedDecisions.includes("reject") && (
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
						)}
					</div>
				</>
			)}
		</div>
	);
}

export const GenericHitlApprovalToolUI: ToolCallMessagePartComponent = ({
	toolName,
	args,
	result,
}) => {
	const { dispatch } = useHitlDecision();

	if (!result || !isInterruptResult(result)) return null;

	return (
		<GenericApprovalCard
			toolName={toolName}
			args={args as Record<string, unknown>}
			interruptData={result}
			onDecision={(decision) => dispatch([decision])}
		/>
	);
};
