"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useSetAtom } from "jotai";
import { CornerDownLeftIcon, Pen } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { openHitlEditPanelAtom } from "@/atoms/chat/hitl-edit-panel.atom";
import { PlateEditor } from "@/components/editor/plate-editor";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useHitlPhase } from "@/hooks/use-hitl-phase";
import { isInterruptResult, useHitlDecision } from "@/lib/hitl";
import type { InterruptResult, HitlDecision } from "@/lib/hitl";

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
	auth_expired?: boolean;
}

type LinearCreateIssueContext = {
	workspaces?: LinearWorkspace[];
	error?: string;
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

interface AuthErrorResult {
	status: "auth_error";
	message: string;
	connector_id?: number;
	connector_type: string;
}

type CreateLinearIssueResult = InterruptResult<LinearCreateIssueContext> | SuccessResult | ErrorResult | AuthErrorResult;

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
	args: { title: string; description?: string };
	interruptData: InterruptResult<LinearCreateIssueContext>;
	onDecision: (decision: HitlDecision) => void;
}) {
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);
	const [isPanelOpen, setIsPanelOpen] = useState(false);
	const openHitlEditPanel = useSetAtom(openHitlEditPanelAtom);
	const [pendingEdits, setPendingEdits] = useState<{ title: string; description: string } | null>(
		null
	);

	const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");
	const [selectedTeamId, setSelectedTeamId] = useState("");
	const [selectedStateId, setSelectedStateId] = useState("__none__");
	const [selectedAssigneeId, setSelectedAssigneeId] = useState("__none__");
	const [selectedPriority, setSelectedPriority] = useState("0");
	const [selectedLabelIds, setSelectedLabelIds] = useState<string[]>([]);

	const workspaces = interruptData.context?.workspaces ?? [];
	const validWorkspaces = useMemo(() => workspaces.filter((w) => !w.auth_expired), [workspaces]);
	const expiredWorkspaces = useMemo(() => workspaces.filter((w) => w.auth_expired), [workspaces]);

	const selectedWorkspace = useMemo(
		() => validWorkspaces.find((w) => String(w.id) === selectedWorkspaceId) ?? null,
		[validWorkspaces, selectedWorkspaceId]
	);

	const selectedTeam = useMemo(
		() => selectedWorkspace?.teams.find((t) => t.id === selectedTeamId) ?? null,
		[selectedWorkspace, selectedTeamId]
	);

	const isTitleValid = (pendingEdits?.title ?? args.title ?? "").trim().length > 0;
	const canApprove = !!selectedWorkspaceId && !!selectedTeamId && isTitleValid;

	const reviewConfig = interruptData.review_configs[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	const buildFinalArgs = useCallback(
		(overrides?: { title?: string; description?: string }) => {
			return {
				title: overrides?.title ?? pendingEdits?.title ?? args.title,
				description:
					overrides?.description ?? pendingEdits?.description ?? args.description ?? null,
				connector_id: selectedWorkspaceId ? Number(selectedWorkspaceId) : null,
				team_id: selectedTeamId || null,
				state_id: selectedStateId === "__none__" ? null : selectedStateId,
				assignee_id: selectedAssigneeId === "__none__" ? null : selectedAssigneeId,
				priority: Number(selectedPriority),
				label_ids: selectedLabelIds,
			};
		},
		[
			args.title,
			args.description,
			selectedWorkspaceId,
			selectedTeamId,
			selectedStateId,
			selectedAssigneeId,
			selectedPriority,
			selectedLabelIds,
			pendingEdits,
		]
	);

	const handleApprove = useCallback(() => {
		if (phase !== "pending") return;
		if (isPanelOpen || !canApprove) return;
		if (!allowedDecisions.includes("approve")) return;
		const isEdited = pendingEdits !== null;
		setProcessing();
		onDecision({
			type: isEdited ? "edit" : "approve",
			edited_action: {
				name: interruptData.action_requests[0].name,
				args: buildFinalArgs(),
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
		buildFinalArgs,
		pendingEdits,
	]);

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
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 transition-[box-shadow] duration-300">
			{/* Header */}
			<div className="flex items-start justify-between px-5 pt-5 pb-4 select-none">
				<div>
					<p className="text-sm font-semibold text-foreground">
						{phase === "rejected"
							? "Linear Issue Rejected"
							: phase === "processing" || phase === "complete"
								? "Linear Issue Approved"
								: "Create Linear Issue"}
					</p>
					{phase === "processing" ? (
						<TextShimmerLoader
							text={pendingEdits ? "Creating issue with your changes" : "Creating issue"}
							size="sm"
						/>
					) : phase === "complete" ? (
						<p className="text-xs text-muted-foreground mt-0.5">
							{pendingEdits ? "Issue created with your changes" : "Issue created"}
						</p>
					) : phase === "rejected" ? (
						<p className="text-xs text-muted-foreground mt-0.5">Issue creation was cancelled</p>
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
								title: pendingEdits?.title ?? args.title ?? "",
								content: pendingEdits?.description ?? args.description ?? "",
								toolName: "Linear Issue",
								onSave: (newTitle, newDescription) => {
									setIsPanelOpen(false);
									setPendingEdits({ title: newTitle, description: newDescription });
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

			{/* Context section — real pickers in pending */}
			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-3 space-y-3 select-none">
						{interruptData.context?.error ? (
							<p className="text-sm text-destructive">{interruptData.context.error}</p>
						) : (
							<>
								{workspaces.length > 0 && (
									<div className="space-y-1.5">
										<p className="text-xs font-medium text-muted-foreground">
											Linear Account <span className="text-destructive">*</span>
										</p>
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
												{validWorkspaces.map((w) => (
													<SelectItem key={w.id} value={String(w.id)}>
														{w.name}
													</SelectItem>
												))}
												{expiredWorkspaces.map((w) => (
													<div
														key={w.id}
														className="relative flex w-full cursor-default items-center gap-2 rounded-sm py-1.5 px-2 text-sm select-none opacity-50 pointer-events-none"
													>
														{w.name} (expired, retry after re-auth)
													</div>
												))}
											</SelectContent>
										</Select>
									</div>
								)}

								{selectedWorkspace && (
									<>
										<div className="space-y-1.5">
											<p className="text-xs font-medium text-muted-foreground">
												Team <span className="text-destructive">*</span>
											</p>
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
													<p className="text-xs font-medium text-muted-foreground">State</p>
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

												<div className="grid grid-cols-2 gap-3">
													<div className="space-y-1.5">
														<p className="text-xs font-medium text-muted-foreground">Assignee</p>
														<Select
															value={selectedAssigneeId}
															onValueChange={setSelectedAssigneeId}
														>
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
														<p className="text-xs font-medium text-muted-foreground">Priority</p>
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
												</div>

												{selectedTeam.labels.length > 0 && (
													<div className="space-y-1.5">
														<p className="text-xs font-medium text-muted-foreground">Labels</p>
														<ToggleGroup
															type="multiple"
															value={selectedLabelIds}
															onValueChange={setSelectedLabelIds}
															className="flex flex-wrap gap-1.5"
														>
															{selectedTeam.labels.map((label) => {
																const isSelected = selectedLabelIds.includes(label.id);
																return (
																	<ToggleGroupItem
																		key={label.id}
																		value={label.id}
																		className="h-auto rounded-full border-0 px-0 py-0 shadow-none hover:bg-transparent data-[state=on]:bg-transparent"
																	>
																		<Badge
																			className={`cursor-pointer rounded-full gap-1 border transition-all ${
																				isSelected
																					? "font-semibold opacity-100 shadow-sm"
																					: "border-transparent opacity-55 hover:opacity-90"
																			}`}
																			style={{
																				backgroundColor: isSelected
																					? `${label.color}70`
																					: `${label.color}28`,
																				color: label.color,
																				borderColor: isSelected
																					? `${label.color}cc`
																					: "transparent",
																			}}
																		>
																			<span
																				className="size-1.5 rounded-full"
																				style={{ backgroundColor: label.color }}
																			/>
																			{label.name}
																		</Badge>
																	</ToggleGroupItem>
																);
															})}
														</ToggleGroup>
													</div>
												)}
											</>
										)}
									</>
								)}
							</>
						)}
					</div>
				</>
			)}

			{/* Content preview */}
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 pt-3">
				{(pendingEdits?.title ?? args.title) != null && (
					<p className="text-sm font-medium text-foreground">{pendingEdits?.title ?? args.title}</p>
				)}
				{(pendingEdits?.description ?? args.description) != null && (
					<div
						className="max-h-[7rem] overflow-hidden text-sm"
						style={{
							maskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
							WebkitMaskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
						}}
					>
						<PlateEditor
							markdown={pendingEdits?.description ?? args.description ?? ""}
							readOnly
							preset="readonly"
							editorVariant="none"
							className="h-auto [&_[data-slate-editor]]:!min-h-0 [&_[data-slate-editor]>*:first-child]:!mt-0"
						/>
					</div>
				)}
			</div>

			{/* Action buttons - only shown when pending */}
			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-3 flex items-center gap-2 select-none">
						{allowedDecisions.includes("approve") && (
							<Button
								size="sm"
								className="rounded-lg gap-1.5"
								onClick={handleApprove}
								disabled={!canApprove || isPanelOpen}
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

function AuthErrorCard({ result }: { result: AuthErrorResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">All Linear accounts expired</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<p className="text-sm text-muted-foreground">{result.message}</p>
			</div>
		</div>
	);
}

function ErrorCard({ result }: { result: ErrorResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">Failed to create Linear issue</p>
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
					{result.message || "Linear issue created successfully"}
				</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4 space-y-2 text-xs">
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

export const CreateLinearIssueToolUI = ({
	args,
	result,
}: ToolCallMessagePartProps<{ title: string; description?: string }, CreateLinearIssueResult>) => {
	const { dispatch } = useHitlDecision();

	if (!result) return null;

	if (isInterruptResult(result)) {
		return (
			<ApprovalCard
				args={args}
				interruptData={result as InterruptResult<LinearCreateIssueContext>}
				onDecision={(decision) => dispatch([decision])}
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
	if (isErrorResult(result)) return <ErrorCard result={result} />;

	return <SuccessCard result={result as SuccessResult} />;
};
