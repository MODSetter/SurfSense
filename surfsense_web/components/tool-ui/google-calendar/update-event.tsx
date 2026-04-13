"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useSetAtom } from "jotai";
import {
	ArrowRightIcon,
	ClockIcon,
	CornerDownLeftIcon,
	MapPinIcon,
	Pen,
	UsersIcon,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import type { ExtraField } from "@/atoms/chat/hitl-edit-panel.atom";
import { openHitlEditPanelAtom } from "@/atoms/chat/hitl-edit-panel.atom";
import { PlateEditor } from "@/components/editor/plate-editor";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import { isInterruptResult, useHitlDecision } from "@/lib/hitl";
import type { HitlDecision, InterruptResult } from "@/lib/hitl";
import { useHitlPhase } from "@/hooks/use-hitl-phase";

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

interface CalendarUpdateEventContext {
	account?: GoogleCalendarAccount;
	event?: CalendarEvent;
	error?: string;
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

interface InsufficientPermissionsResult {
	status: "insufficient_permissions";
	connector_id: number;
	message: string;
}

type UpdateCalendarEventResult =
	| InterruptResult<CalendarUpdateEventContext>
	| SuccessResult
	| ErrorResult
	| NotFoundResult
	| InsufficientPermissionsResult
	| AuthErrorResult;

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

function isInsufficientPermissionsResult(result: unknown): result is InsufficientPermissionsResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as InsufficientPermissionsResult).status === "insufficient_permissions"
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
	args,
	interruptData,
	onDecision,
}: {
	args: {
		event_ref: string;
		new_summary?: string;
		new_description?: string;
		new_start_datetime?: string;
		new_end_datetime?: string;
		new_location?: string;
		new_attendees?: string[];
	};
	interruptData: InterruptResult<CalendarUpdateEventContext>;
	onDecision: (decision: HitlDecision) => void;
}) {
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);
	const actionArgs = interruptData.action_requests[0]?.args ?? {};
	const context = interruptData.context;
	const account = context?.account;
	const event = context?.event;

	const [isPanelOpen, setIsPanelOpen] = useState(false);
	const [wasEdited, setWasEdited] = useState(false);
	const openHitlEditPanel = useSetAtom(openHitlEditPanelAtom);
	const [pendingEdits, setPendingEdits] = useState<{
		summary: string;
		description: string;
		start_datetime: string;
		end_datetime: string;
		location: string;
		attendees: string;
	} | null>(null);

	const reviewConfig = interruptData.review_configs[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	const currentAttendees = event?.attendees?.map((a) => a.email) ?? [];
	const proposedAttendees = Array.isArray(actionArgs.new_attendees)
		? (actionArgs.new_attendees as string[])
		: null;

	const effectiveNewSummary = actionArgs.new_summary ?? args.new_summary;
	const effectiveNewStartDatetime = actionArgs.new_start_datetime ?? args.new_start_datetime;
	const effectiveNewEndDatetime = actionArgs.new_end_datetime ?? args.new_end_datetime;
	const effectiveNewLocation =
		actionArgs.new_location !== undefined ? actionArgs.new_location : args.new_location;
	const effectiveNewAttendees =
		proposedAttendees ?? (Array.isArray(args.new_attendees) ? args.new_attendees : null);
	const effectiveNewDescription =
		actionArgs.new_description !== undefined ? actionArgs.new_description : args.new_description;

	const changes: Array<{ label: string; oldVal: string; newVal: string }> = [];

	if (effectiveNewSummary && String(effectiveNewSummary) !== (event?.summary ?? "")) {
		changes.push({
			label: "Summary",
			oldVal: event?.summary ?? "",
			newVal: String(effectiveNewSummary),
		});
	}
	if (effectiveNewStartDatetime && String(effectiveNewStartDatetime) !== (event?.start ?? "")) {
		changes.push({
			label: "Start",
			oldVal: event?.start ? formatDateTime(event.start) : "",
			newVal: formatDateTime(String(effectiveNewStartDatetime)),
		});
	}
	if (effectiveNewEndDatetime && String(effectiveNewEndDatetime) !== (event?.end ?? "")) {
		changes.push({
			label: "End",
			oldVal: event?.end ? formatDateTime(event.end) : "",
			newVal: formatDateTime(String(effectiveNewEndDatetime)),
		});
	}
	if (
		effectiveNewLocation !== undefined &&
		String(effectiveNewLocation ?? "") !== (event?.location ?? "")
	) {
		changes.push({
			label: "Location",
			oldVal: event?.location ?? "",
			newVal: String(effectiveNewLocation ?? ""),
		});
	}
	if (effectiveNewAttendees) {
		const oldStr = currentAttendees.join(", ");
		const newStr = effectiveNewAttendees.join(", ");
		if (oldStr !== newStr) {
			changes.push({ label: "Attendees", oldVal: oldStr, newVal: newStr });
		}
	}

	const hasDescriptionChange =
		effectiveNewDescription !== undefined &&
		String(effectiveNewDescription ?? "") !== (event?.description ?? "");

	const buildFinalArgs = useCallback(() => {
		const base = {
			event_id: event?.event_id,
			document_id: event?.document_id,
			connector_id: account?.id,
		};

		if (pendingEdits) {
			const attendeesArr = pendingEdits.attendees
				? pendingEdits.attendees
						.split(",")
						.map((e) => e.trim())
						.filter(Boolean)
				: null;
			const origAttendees = event?.attendees?.map((a) => a.email) ?? [];

			return {
				...base,
				new_summary:
					pendingEdits.summary && pendingEdits.summary !== (event?.summary ?? "")
						? pendingEdits.summary
						: null,
				new_description:
					pendingEdits.description !== (event?.description ?? "")
						? pendingEdits.description || null
						: null,
				new_start_datetime:
					pendingEdits.start_datetime && pendingEdits.start_datetime !== (event?.start ?? "")
						? pendingEdits.start_datetime
						: null,
				new_end_datetime:
					pendingEdits.end_datetime && pendingEdits.end_datetime !== (event?.end ?? "")
						? pendingEdits.end_datetime
						: null,
				new_location:
					pendingEdits.location !== (event?.location ?? "") ? pendingEdits.location || null : null,
				new_attendees:
					attendeesArr && attendeesArr.join(",") !== origAttendees.join(",") ? attendeesArr : null,
			};
		}
		return {
			...base,
			new_summary: actionArgs.new_summary ?? null,
			new_description: actionArgs.new_description ?? null,
			new_start_datetime: actionArgs.new_start_datetime ?? null,
			new_end_datetime: actionArgs.new_end_datetime ?? null,
			new_location: actionArgs.new_location ?? null,
			new_attendees: proposedAttendees ?? null,
		};
	}, [event, account, actionArgs, proposedAttendees, pendingEdits]);

	const handleApprove = useCallback(() => {
		if (phase !== "pending" || isPanelOpen) return;
		if (!allowedDecisions.includes("approve")) return;
		const isEdited = pendingEdits !== null;
		setWasEdited(isEdited);
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
		isPanelOpen,
		allowedDecisions,
		setProcessing,
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
				<div className="flex items-center gap-2">
					<div>
						<p className="text-sm font-semibold text-foreground">
							{phase === "rejected"
								? "Calendar Event Update Rejected"
								: phase === "processing" || phase === "complete"
									? "Calendar Event Update Approved"
									: "Update Calendar Event"}
						</p>
						{phase === "processing" ? (
							<TextShimmerLoader
								text={wasEdited ? "Updating event with your changes" : "Updating event"}
								size="sm"
							/>
						) : phase === "complete" ? (
							<p className="text-xs text-muted-foreground mt-0.5">
								{wasEdited ? "Event updated with your changes" : "Event updated"}
							</p>
						) : phase === "rejected" ? (
							<p className="text-xs text-muted-foreground mt-0.5">Event update was cancelled</p>
						) : (
							<p className="text-xs text-muted-foreground mt-0.5">
								Requires your approval to proceed
							</p>
						)}
					</div>
				</div>
				{phase === "pending" && canEdit && (
					<Button
						size="sm"
						variant="ghost"
						className="rounded-lg text-muted-foreground -mt-1 -mr-2"
						onClick={() => {
							setIsPanelOpen(true);
							const proposedSummary =
								pendingEdits?.summary ??
								(actionArgs.new_summary ? String(actionArgs.new_summary) : (event?.summary ?? ""));
							const proposedDescription =
								pendingEdits?.description ??
								(actionArgs.new_description
									? String(actionArgs.new_description)
									: (event?.description ?? ""));
							const proposedStart =
								pendingEdits?.start_datetime ??
								(actionArgs.new_start_datetime
									? String(actionArgs.new_start_datetime)
									: (event?.start ?? ""));
							const proposedEnd =
								pendingEdits?.end_datetime ??
								(actionArgs.new_end_datetime
									? String(actionArgs.new_end_datetime)
									: (event?.end ?? ""));
							const proposedLocation =
								pendingEdits?.location ??
								(actionArgs.new_location !== undefined
									? String(actionArgs.new_location ?? "")
									: (event?.location ?? ""));
							const proposedAttendeesStr =
								pendingEdits?.attendees ??
								(proposedAttendees ? proposedAttendees.join(", ") : currentAttendees.join(", "));

							const extraFields: ExtraField[] = [
								{
									key: "start_datetime",
									label: "Start",
									type: "datetime-local",
									value: proposedStart,
								},
								{ key: "end_datetime", label: "End", type: "datetime-local", value: proposedEnd },
								{ key: "location", label: "Location", type: "text", value: proposedLocation },
								{
									key: "attendees",
									label: "Attendees",
									type: "emails",
									value: proposedAttendeesStr,
								},
							];
							openHitlEditPanel({
								title: proposedSummary,
								content: proposedDescription,
								toolName: "Calendar Event",
								extraFields,
								onSave: (newTitle, newContent, extraFieldValues) => {
									setIsPanelOpen(false);
									const extras = extraFieldValues ?? {};
									setPendingEdits({
										summary: newTitle,
										description: newContent,
										start_datetime: extras.start_datetime ?? proposedStart,
										end_datetime: extras.end_datetime ?? proposedEnd,
										location: extras.location ?? proposedLocation,
										attendees: extras.attendees ?? proposedAttendeesStr,
									});
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

			{/* Content section */}
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4 space-y-4 select-none">
				{context?.error ? (
					<p className="text-sm text-destructive">{context.error}</p>
				) : (
					<>
						{phase === "pending" && account && (
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

						{/* Proposed Changes - visible in all phases */}
						{(changes.length > 0 || hasDescriptionChange) && (
							<div className="space-y-2">
								<p className="text-xs font-medium text-muted-foreground">Proposed Changes</p>
								<div className="space-y-2">
									{changes.map((change) => (
										<div key={change.label} className="text-xs space-y-0.5">
											<span className="text-muted-foreground">{change.label}</span>
											<div className="flex items-center gap-1.5 flex-wrap">
												<span className="text-muted-foreground line-through">
													{change.oldVal || "(empty)"}
												</span>
												<ArrowRightIcon className="size-3 text-muted-foreground shrink-0" />
												<span className="font-medium text-foreground">
													{change.newVal || "(empty)"}
												</span>
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
													WebkitMaskImage:
														"linear-gradient(to bottom, black 50%, transparent 100%)",
												}}
											>
												<PlateEditor
													markdown={String(effectiveNewDescription ?? "")}
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

						{event && changes.length === 0 && !hasDescriptionChange && (
							<p className="text-sm text-muted-foreground italic">No changes proposed</p>
						)}
					</>
				)}
			</div>

			{/* Action buttons - pending only */}
			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 flex items-center gap-2 select-none">
						{allowedDecisions.includes("approve") && (
							<Button
								size="sm"
								className="rounded-lg gap-1.5"
								onClick={handleApprove}
								disabled={isPanelOpen}
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

function InsufficientPermissionsCard({ result }: { result: InsufficientPermissionsResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">
					Additional Google Calendar permissions required
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

export const UpdateCalendarEventToolUI = ({
	args,
	result,
}: ToolCallMessagePartProps<
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
>) => {
	const { dispatch } = useHitlDecision();

	if (!result) return null;

	if (isInterruptResult(result)) {
		return (
			<ApprovalCard
				args={args}
				interruptData={result as InterruptResult<CalendarUpdateEventContext>}
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

	if (isNotFoundResult(result)) return <NotFoundCard result={result} />;
	if (isAuthErrorResult(result)) return <AuthErrorCard result={result} />;
	if (isInsufficientPermissionsResult(result))
		return <InsufficientPermissionsCard result={result} />;
	if (isErrorResult(result)) return <ErrorCard result={result} />;

	return <SuccessCard result={result as SuccessResult} />;
};
