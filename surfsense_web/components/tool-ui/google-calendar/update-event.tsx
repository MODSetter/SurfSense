"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
	CalendarIcon,
	ClockIcon,
	MapPinIcon,
	UsersIcon,
	ArrowRightIcon,
	CornerDownLeftIcon,
	Pen,
	TriangleAlertIcon,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useSetAtom } from "jotai";
import { Button } from "@/components/ui/button";
import { PlateEditor } from "@/components/editor/plate-editor";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { openHitlEditPanelAtom } from "@/atoms/chat/hitl-edit-panel.atom";
import type { ExtraField } from "@/atoms/chat/hitl-edit-panel.atom";

interface GoogleCalendarAccount {
	id: number;
	name: string;
	auth_expired?: boolean;
}

interface CalendarEvent {
	event_id: string;
	summary: string;
	start: string;
	end: string;
	description?: string;
	location?: string;
	attendees?: Array<{ email: string }>;
	calendar_id: string;
	document_id: number;
	indexed_at?: string;
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
		account?: GoogleCalendarAccount;
		event?: CalendarEvent;
		error?: string;
	};
}

interface SuccessResult {
	status: "success";
	event_id: string;
	html_link?: string;
	message?: string;
}

interface ErrorResult {
	status: "error";
	message: string;
}

interface NotFoundResult {
	status: "not_found";
	message: string;
}

interface AuthErrorResult {
	status: "auth_error";
	message: string;
	connector_type?: string;
}

type UpdateCalendarEventResult =
	| InterruptResult
	| SuccessResult
	| ErrorResult
	| NotFoundResult
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

function isNotFoundResult(result: unknown): result is NotFoundResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as NotFoundResult).status === "not_found"
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

function formatDateTime(iso: string): string {
	try {
		return new Date(iso).toLocaleString(undefined, {
			dateStyle: "medium",
			timeStyle: "short",
		});
	} catch {
		return iso;
	}
}

function ApprovalCard({
	interruptData,
	onDecision,
}: {
	interruptData: InterruptResult;
	onDecision: (decision: {
		type: "approve" | "reject" | "edit";
		message?: string;
		edited_action?: { name: string; args: Record<string, unknown> };
	}) => void;
}) {
	const actionArgs = interruptData.action_requests[0]?.args ?? {};
	const context = interruptData.context;
	const account = context?.account;
	const event = context?.event;

	const [decided, setDecided] = useState<"approve" | "reject" | "edit" | null>(
		interruptData.__decided__ ?? null
	);
	const [isPanelOpen, setIsPanelOpen] = useState(false);
	const openHitlEditPanel = useSetAtom(openHitlEditPanelAtom);

	const reviewConfig = interruptData.review_configs[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	const currentAttendees = event?.attendees?.map((a) => a.email) ?? [];
	const proposedAttendees = Array.isArray(actionArgs.new_attendees)
		? (actionArgs.new_attendees as string[])
		: null;

	const changes: Array<{ label: string; oldVal: string; newVal: string }> = [];

	if (actionArgs.new_summary && String(actionArgs.new_summary) !== event?.summary) {
		changes.push({ label: "Summary", oldVal: event?.summary ?? "", newVal: String(actionArgs.new_summary) });
	}
	if (actionArgs.new_start_datetime && String(actionArgs.new_start_datetime) !== event?.start) {
		changes.push({
			label: "Start",
			oldVal: event?.start ? formatDateTime(event.start) : "",
			newVal: formatDateTime(String(actionArgs.new_start_datetime)),
		});
	}
	if (actionArgs.new_end_datetime && String(actionArgs.new_end_datetime) !== event?.end) {
		changes.push({
			label: "End",
			oldVal: event?.end ? formatDateTime(event.end) : "",
			newVal: formatDateTime(String(actionArgs.new_end_datetime)),
		});
	}
	if (actionArgs.new_location !== undefined && String(actionArgs.new_location ?? "") !== (event?.location ?? "")) {
		changes.push({ label: "Location", oldVal: event?.location ?? "", newVal: String(actionArgs.new_location ?? "") });
	}
	if (proposedAttendees) {
		const oldStr = currentAttendees.join(", ");
		const newStr = proposedAttendees.join(", ");
		if (oldStr !== newStr) {
			changes.push({ label: "Attendees", oldVal: oldStr, newVal: newStr });
		}
	}

	const hasDescriptionChange =
		actionArgs.new_description !== undefined &&
		String(actionArgs.new_description ?? "") !== (event?.description ?? "");

	const buildFinalArgs = useCallback(() => {
		return {
			event_id: event?.event_id,
			document_id: event?.document_id,
			connector_id: account?.id,
			new_summary: actionArgs.new_summary ?? null,
			new_description: actionArgs.new_description ?? null,
			new_start_datetime: actionArgs.new_start_datetime ?? null,
			new_end_datetime: actionArgs.new_end_datetime ?? null,
			new_location: actionArgs.new_location ?? null,
			new_attendees: proposedAttendees ?? null,
		};
	}, [event, account, actionArgs, proposedAttendees]);

	const handleApprove = useCallback(() => {
		if (decided || isPanelOpen) return;
		if (!allowedDecisions.includes("approve")) return;
		setDecided("approve");
		onDecision({
			type: "approve",
			edited_action: {
				name: interruptData.action_requests[0].name,
				args: buildFinalArgs(),
			},
		});
	}, [decided, isPanelOpen, allowedDecisions, onDecision, interruptData, buildFinalArgs]);

	useEffect(() => {
		const handler = (e: KeyboardEvent) => {
			if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
				handleApprove();
			}
		};
		window.addEventListener("keydown", handler);
		return () => window.removeEventListener("keydown", handler);
	}, [handleApprove]);

	if (decided && decided !== "reject") return null;

	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 transition-all duration-300">
			{/* Header */}
			<div className="flex items-start justify-between px-5 pt-5 pb-4 select-none">
				<div className="flex items-center gap-2">
					<CalendarIcon className="size-4 text-muted-foreground shrink-0" />
					<div>
						<p className="text-sm font-semibold text-foreground">
							{decided === "reject"
								? "Calendar Event Update Rejected"
								: decided === "approve" || decided === "edit"
									? "Calendar Event Update Approved"
									: "Update Calendar Event"}
						</p>
						<p className="text-xs text-muted-foreground mt-0.5">
							{decided === "reject"
								? "Event update was cancelled"
								: decided === "edit"
									? "Event update is in progress with your changes"
									: decided === "approve"
										? "Event update is in progress"
										: "Requires your approval to proceed"}
						</p>
					</div>
				</div>
				{!decided && canEdit && (
					<Button
						size="sm"
						variant="ghost"
						className="rounded-lg text-muted-foreground -mt-1 -mr-2"
						onClick={() => {
							setIsPanelOpen(true);
							const proposedSummary = actionArgs.new_summary
								? String(actionArgs.new_summary)
								: (event?.summary ?? "");
							const proposedDescription = actionArgs.new_description
								? String(actionArgs.new_description)
								: (event?.description ?? "");
							const proposedStart = actionArgs.new_start_datetime
								? String(actionArgs.new_start_datetime)
								: (event?.start ?? "");
							const proposedEnd = actionArgs.new_end_datetime
								? String(actionArgs.new_end_datetime)
								: (event?.end ?? "");
							const proposedLocation = actionArgs.new_location !== undefined
								? String(actionArgs.new_location ?? "")
								: (event?.location ?? "");
							const proposedAttendeesStr = proposedAttendees
								? proposedAttendees.join(", ")
								: currentAttendees.join(", ");

							const extraFields: ExtraField[] = [
								{ key: "start_datetime", label: "Start", type: "datetime-local", value: proposedStart },
								{ key: "end_datetime", label: "End", type: "datetime-local", value: proposedEnd },
								{ key: "location", label: "Location", type: "text", value: proposedLocation },
								{ key: "attendees", label: "Attendees (comma-separated emails)", type: "text", value: proposedAttendeesStr },
							];
							openHitlEditPanel({
								title: proposedSummary,
								content: proposedDescription,
								toolName: "Calendar Event",
								extraFields,
								onSave: (newTitle, newContent, extraFieldValues) => {
									setIsPanelOpen(false);
									setDecided("edit");

									const editedArgs: Record<string, unknown> = {
										event_id: event?.event_id,
										document_id: event?.document_id,
										connector_id: account?.id,
										new_summary: newTitle || null,
										new_description: newContent || null,
									};

									if (extraFieldValues) {
										editedArgs.new_start_datetime = extraFieldValues.start_datetime || null;
										editedArgs.new_end_datetime = extraFieldValues.end_datetime || null;
										editedArgs.new_location = extraFieldValues.location || null;
										if (extraFieldValues.attendees !== undefined) {
											editedArgs.new_attendees = extraFieldValues.attendees
												.split(",")
												.map((e) => e.trim())
												.filter(Boolean);
										}
									}

									onDecision({
										type: "edit",
										edited_action: {
											name: interruptData.action_requests[0].name,
											args: editedArgs,
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
			{!decided && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 space-y-4 select-none">
						{context?.error ? (
							<p className="text-sm text-destructive">{context.error}</p>
						) : (
							<>
								{account && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">Google Calendar Account</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm">
											{account.name}
										</div>
									</div>
								)}

								{event && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">Current Event</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm space-y-1.5">
											<div className="font-medium">{event.summary}</div>
											{(event.start || event.end) && (
												<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
													<ClockIcon className="size-3 shrink-0" />
													<span>
														{event.start ? formatDateTime(event.start) : ""}
														{event.start && event.end ? " — " : ""}
														{event.end ? formatDateTime(event.end) : ""}
													</span>
												</div>
											)}
											{event.location && (
												<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
													<MapPinIcon className="size-3 shrink-0" />
													<span>{event.location}</span>
												</div>
											)}
											{currentAttendees.length > 0 && (
												<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
													<UsersIcon className="size-3 shrink-0" />
													<span>{currentAttendees.join(", ")}</span>
												</div>
											)}
										</div>
									</div>
								)}

								{(changes.length > 0 || hasDescriptionChange) && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">Proposed Changes</p>
										<div className="space-y-2">
											{changes.map((change) => (
												<div key={change.label} className="text-xs space-y-0.5">
													<span className="text-muted-foreground">{change.label}</span>
													<div className="flex items-center gap-1.5 flex-wrap">
														<span className="text-muted-foreground line-through">{change.oldVal || "(empty)"}</span>
														<ArrowRightIcon className="size-3 text-muted-foreground shrink-0" />
														<span className="font-medium text-foreground">{change.newVal || "(empty)"}</span>
													</div>
												</div>
											))}
											{hasDescriptionChange && (
												<div className="text-xs space-y-0.5">
													<span className="text-muted-foreground">Description</span>
													<div
														className="mt-1 max-h-[5rem] overflow-hidden"
														style={{
															maskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
															WebkitMaskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
														}}
													>
														<PlateEditor
															markdown={String(actionArgs.new_description ?? "")}
															readOnly
															preset="readonly"
															editorVariant="none"
															className="h-auto [&_[data-slate-editor]]:!min-h-0 [&_[data-slate-editor]>*:first-child]:!mt-0"
														/>
													</div>
												</div>
											)}
										</div>
									</div>
								)}

								{changes.length === 0 && !hasDescriptionChange && (
									<p className="text-sm text-muted-foreground italic">No changes proposed</p>
								)}
							</>
						)}
					</div>
				</>
			)}

			{/* Action buttons */}
			{!decided && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 flex items-center gap-2 select-none">
						{allowedDecisions.includes("approve") && (
							<Button
								size="sm"
								className="rounded-lg gap-1.5"
								onClick={handleApprove}
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

function ErrorCard({ result }: { result: ErrorResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">Failed to update calendar event</p>
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
				<p className="text-sm font-semibold text-destructive">
					Google Calendar authentication expired
				</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<p className="text-sm text-muted-foreground">{result.message}</p>
			</div>
		</div>
	);
}

function NotFoundCard({ result }: { result: NotFoundResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border border-amber-500/50 bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<div className="flex items-center gap-2">
					<TriangleAlertIcon className="size-4 text-amber-500 shrink-0" />
					<p className="text-sm font-semibold text-amber-600 dark:text-amber-400">
						Event not found
					</p>
				</div>
			</div>
			<div className="mx-5 h-px bg-amber-500/30" />
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
					{result.message || "Calendar event updated successfully"}
				</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4 space-y-2 text-xs">
				{result.html_link && (
					<div>
						<a
							href={result.html_link}
							target="_blank"
							rel="noopener noreferrer"
							className="text-primary hover:underline"
						>
							Open in Google Calendar
						</a>
					</div>
				)}
			</div>
		</div>
	);
}

export const UpdateCalendarEventToolUI = makeAssistantToolUI<
	{
		event_ref: string;
		new_summary?: string;
		new_description?: string;
		new_start_datetime?: string;
		new_end_datetime?: string;
		new_location?: string;
		new_attendees?: string[];
	},
	UpdateCalendarEventResult
>({
	toolName: "update_calendar_event",
	render: function UpdateCalendarEventUI({ result, status }) {
		if (status.type === "running") {
			return (
				<div className="my-4 max-w-lg rounded-2xl border bg-muted/30 px-5 py-4 select-none">
					<TextShimmerLoader text="Looking up calendar event..." size="sm" />
				</div>
			);
		}

		if (!result) return null;

		if (isInterruptResult(result)) {
			return (
				<ApprovalCard
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

		if (isNotFoundResult(result)) return <NotFoundCard result={result} />;
		if (isAuthErrorResult(result)) return <AuthErrorCard result={result} />;
		if (isErrorResult(result)) return <ErrorCard result={result} />;

		return <SuccessCard result={result as SuccessResult} />;
	},
});
