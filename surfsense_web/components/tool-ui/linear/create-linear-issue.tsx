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

interface LinearLabel {
	id: string;
	name: string;
	color: string;
}

interface LinearState {
	id: string;
	name: string;
	type: string;
	color: string;
	position: number;
}

interface LinearMember {
	id: string;
	name: string;
	displayName: string;
	email: string;
	active: boolean;
}

interface LinearTeam {
	id: string;
	name: string;
	key: string;
	states: LinearState[];
	members: LinearMember[];
	labels: LinearLabel[];
}

interface LinearPriority {
	priority: number;
	label: string;
}

interface LinearWorkspace {
	id: number;
	name: string;
	organization_name: string;
	teams: LinearTeam[];
	priorities: LinearPriority[];
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
	interrupt_type?: string;
	context?: {
		workspaces?: LinearWorkspace[];
		error?: string;
	};
}

interface SuccessResult {
	status: "success";
	issue_id: string;
	identifier: string;
	url: string;
	message?: string;
}

interface ErrorResult {
	status: "error";
	message: string;
}

type CreateLinearIssueResult = InterruptResult | SuccessResult | ErrorResult;

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
	args: { title: string; description?: string };
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
	const [editedTitle, setEditedTitle] = useState(args.title ?? "");
	const [editedDescription, setEditedDescription] = useState(args.description ?? "");
	const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");
	const [selectedTeamId, setSelectedTeamId] = useState("");
	const [selectedStateId, setSelectedStateId] = useState("__none__");
	const [selectedAssigneeId, setSelectedAssigneeId] = useState("__none__");
	const [selectedPriority, setSelectedPriority] = useState("0");
	const [selectedLabelIds, setSelectedLabelIds] = useState<string[]>([]);

	const workspaces = interruptData.context?.workspaces ?? [];

	const selectedWorkspace = useMemo(
		() => workspaces.find((w) => String(w.id) === selectedWorkspaceId) ?? null,
		[workspaces, selectedWorkspaceId]
	);

	const selectedTeam = useMemo(
		() => selectedWorkspace?.teams.find((t) => t.id === selectedTeamId) ?? null,
		[selectedWorkspace, selectedTeamId]
	);

	const isTitleValid = editedTitle.trim().length > 0;
	const canApprove = !!selectedWorkspaceId && !!selectedTeamId && isTitleValid;

	const reviewConfig = interruptData.review_configs[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	function buildFinalArgs() {
		return {
			title: editedTitle,
			description: editedDescription || null,
			connector_id: selectedWorkspaceId ? Number(selectedWorkspaceId) : null,
			team_id: selectedTeamId || null,
			state_id: selectedStateId === "__none__" ? null : selectedStateId,
			assignee_id: selectedAssigneeId === "__none__" ? null : selectedAssigneeId,
			priority: Number(selectedPriority),
			label_ids: selectedLabelIds,
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
					<p className="text-sm font-medium text-foreground">Create Linear Issue</p>
					<p className="truncate text-xs text-muted-foreground">
						{isEditing ? "You can edit the arguments below" : "Requires your approval to proceed"}
					</p>
				</div>
			</div>

			{/* Context section */}
			{!decided && (
				<div className="border-b border-border px-4 py-3 bg-muted/30 space-y-3">
					{interruptData.context?.error ? (
						<p className="text-sm text-destructive">{interruptData.context.error}</p>
					) : (
						<>
							{workspaces.length > 0 && (
								<div className="space-y-1.5">
									<div className="text-xs font-medium text-muted-foreground">
										Linear Account <span className="text-destructive">*</span>
									</div>
									<Select
										value={selectedWorkspaceId}
										onValueChange={(v) => {
											setSelectedWorkspaceId(v);
											setSelectedTeamId("");
											setSelectedStateId("__none__");
											setSelectedAssigneeId("__none__");
											setSelectedPriority("0");
											setSelectedLabelIds([]);
										}}
									>
										<SelectTrigger className="w-full">
											<SelectValue placeholder="Select an account" />
										</SelectTrigger>
										<SelectContent>
											{workspaces.map((w) => (
												<SelectItem key={w.id} value={String(w.id)}>
													{w.name}
												</SelectItem>
											))}
										</SelectContent>
									</Select>
								</div>
							)}

							{selectedWorkspace && (
								<>
									<div className="space-y-1.5">
										<div className="text-xs font-medium text-muted-foreground">
											Team <span className="text-destructive">*</span>
										</div>
										<Select
											value={selectedTeamId}
											onValueChange={(v) => {
												setSelectedTeamId(v);
												const newTeam = selectedWorkspace.teams.find((t) => t.id === v);
												setSelectedStateId(newTeam?.states?.[0]?.id ?? "__none__");
												setSelectedAssigneeId("__none__");
												setSelectedLabelIds([]);
											}}
										>
											<SelectTrigger className="w-full">
												<SelectValue placeholder="Select a team" />
											</SelectTrigger>
											<SelectContent>
												{selectedWorkspace.teams.map((t) => (
													<SelectItem key={t.id} value={t.id}>
														{t.name} ({t.key})
													</SelectItem>
												))}
											</SelectContent>
										</Select>
									</div>

									{selectedTeam && (
										<>
											<div className="space-y-1.5">
												<div className="text-xs font-medium text-muted-foreground">State</div>
												<Select value={selectedStateId} onValueChange={setSelectedStateId}>
													<SelectTrigger className="w-full">
														<SelectValue placeholder="Default" />
													</SelectTrigger>
													<SelectContent>
														{selectedTeam.states.map((s) => (
															<SelectItem key={s.id} value={s.id}>
																{s.name}
															</SelectItem>
														))}
													</SelectContent>
												</Select>
											</div>

											<div className="space-y-1.5">
												<div className="text-xs font-medium text-muted-foreground">Assignee</div>
												<Select value={selectedAssigneeId} onValueChange={setSelectedAssigneeId}>
													<SelectTrigger className="w-full">
														<SelectValue placeholder="Unassigned" />
													</SelectTrigger>
													<SelectContent>
														<SelectItem value="__none__">Unassigned</SelectItem>
														{selectedTeam.members
															.filter((m) => m.active)
															.map((m) => (
																<SelectItem key={m.id} value={m.id}>
																	{m.name} ({m.email})
																</SelectItem>
															))}
													</SelectContent>
												</Select>
											</div>

											<div className="space-y-1.5">
												<div className="text-xs font-medium text-muted-foreground">Priority</div>
												<Select value={selectedPriority} onValueChange={setSelectedPriority}>
													<SelectTrigger className="w-full">
														<SelectValue placeholder="No priority" />
													</SelectTrigger>
													<SelectContent>
														{selectedWorkspace.priorities.map((p) => (
															<SelectItem key={p.priority} value={String(p.priority)}>
																{p.label}
															</SelectItem>
														))}
													</SelectContent>
												</Select>
											</div>

											{selectedTeam.labels.length > 0 && (
												<div className="space-y-1.5">
													<div className="text-xs font-medium text-muted-foreground">Labels</div>
													<div className="flex flex-wrap gap-1.5">
														{selectedTeam.labels.map((label) => {
															const isSelected = selectedLabelIds.includes(label.id);
															return (
																<button
																	key={label.id}
																	type="button"
																	onClick={() =>
																		setSelectedLabelIds((prev) =>
																			isSelected
																				? prev.filter((id) => id !== label.id)
																				: [...prev, label.id]
																		)
																	}
																	className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium transition-opacity ${
																		isSelected
																			? "opacity-100 ring-2 ring-foreground/30"
																			: "opacity-50 hover:opacity-80"
																	}`}
																	style={{
																		backgroundColor: `${label.color}33`,
																		color: label.color,
																	}}
																>
																	<span
																		className="size-1.5 rounded-full"
																		style={{ backgroundColor: label.color }}
																	/>
																	{label.name}
																</button>
															);
														})}
													</div>
												</div>
											)}
										</>
									)}
								</>
							)}
						</>
					)}
				</div>
			)}

			{/* Display mode */}
			{!isEditing && (
				<div className="space-y-2 px-4 py-3 bg-card">
					<div>
						<p className="text-xs font-medium text-muted-foreground">Title</p>
						<p className="text-sm text-foreground">{args.title}</p>
					</div>
					{args.description && (
						<div>
							<p className="text-xs font-medium text-muted-foreground">Description</p>
							<p className="line-clamp-4 text-sm whitespace-pre-wrap text-foreground">
								{args.description}
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
							htmlFor="linear-title"
							className="text-xs font-medium text-muted-foreground mb-1.5 block"
						>
							Title <span className="text-destructive">*</span>
						</label>
						<Input
							id="linear-title"
							value={editedTitle}
							onChange={(e) => setEditedTitle(e.target.value)}
							placeholder="Enter issue title"
							className={!isTitleValid ? "border-destructive" : ""}
						/>
						{!isTitleValid && <p className="text-xs text-destructive mt-1">Title is required</p>}
					</div>
					<div>
						<label
							htmlFor="linear-description"
							className="text-xs font-medium text-muted-foreground mb-1.5 block"
						>
							Description
						</label>
						<Textarea
							id="linear-description"
							value={editedDescription}
							onChange={(e) => setEditedDescription(e.target.value)}
							placeholder="Enter issue description (markdown supported)"
							rows={5}
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
								setIsEditing(false);
								onDecision({
									type: "edit",
									edited_action: {
										name: interruptData.action_requests[0].name,
										args: buildFinalArgs(),
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
								setEditedTitle(args.title ?? "");
								setEditedDescription(args.description ?? "");
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
											args: buildFinalArgs(),
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

function ErrorCard({ result }: { result: ErrorResult }) {
	return (
		<div className="my-4 max-w-md overflow-hidden rounded-xl border border-destructive/50 bg-card">
			<div className="flex items-center gap-3 border-b border-destructive/50 px-4 py-3">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-destructive/10">
					<XIcon className="size-4 text-destructive" />
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-sm font-medium text-destructive">Failed to create Linear issue</p>
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
						{result.message || "Linear issue created successfully"}
					</p>
				</div>
			</div>
			<div className="space-y-2 px-4 py-3 text-xs">
				<div>
					<span className="font-medium text-muted-foreground">Identifier: </span>
					<span>{result.identifier}</span>
				</div>
				{result.url && (
					<div>
						<a
							href={result.url}
							target="_blank"
							rel="noopener noreferrer"
							className="text-primary hover:underline"
						>
							Open in Linear
						</a>
					</div>
				)}
			</div>
		</div>
	);
}

export const CreateLinearIssueToolUI = makeAssistantToolUI<
	{ title: string; description?: string },
	CreateLinearIssueResult
>({
	toolName: "create_linear_issue",
	render: function CreateLinearIssueUI({ args, result, status }) {
		if (status.type === "running") {
			return (
				<div className="my-4 flex max-w-md items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
					<Loader2Icon className="size-4 animate-spin text-muted-foreground" />
					<p className="text-sm text-muted-foreground">Preparing Linear issue...</p>
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

		if (isErrorResult(result)) return <ErrorCard result={result} />;

		return <SuccessCard result={result as SuccessResult} />;
	},
});
