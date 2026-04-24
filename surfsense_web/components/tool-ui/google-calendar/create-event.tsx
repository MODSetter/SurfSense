"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useSetAtom } from "jotai";
import {
	ClockIcon,
	CornerDownLeftIcon,
	GlobeIcon,
	MapPinIcon,
	Pencil,
	UsersIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ExtraField } from "@/atoms/chat/hitl-edit-panel.atom";
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
import type { HitlDecision, InterruptResult } from "@/lib/hitl";
import { isInterruptResult, useHitlDecision } from "@/lib/hitl";

interface GoogleCalendarAccount {
	id: number;
	name: string;
	auth_expired?: boolean;
}

interface CalendarEntry {
	id: string;
	summary: string;
	primary?: boolean;
}

type CalendarCreateEventContext = {
	accounts?: GoogleCalendarAccount[];
	calendars?: CalendarEntry[];
	timezone?: string;
	error?: string;
};

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

type CreateCalendarEventResult =
	| InterruptResult<CalendarCreateEventContext>
	| SuccessResult
	| ErrorResult
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
		summary: string;
		start_datetime: string;
		end_datetime: string;
		description?: string;
		location?: string;
		attendees?: string[];
	};
	interruptData: InterruptResult<CalendarCreateEventContext>;
	onDecision: (decision: HitlDecision) => void;
}) {
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);
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

	const accounts = interruptData.context?.accounts ?? [];
	const validAccounts = accounts.filter((a) => !a.auth_expired);
	const expiredAccounts = accounts.filter((a) => a.auth_expired);
	const calendars = interruptData.context?.calendars ?? [];
	const timezone = interruptData.context?.timezone ?? "";

	const defaultAccountId = useMemo(() => {
		if (validAccounts.length === 1) return String(validAccounts[0].id);
		return "";
	}, [validAccounts]);

	const defaultCalendarId = useMemo(() => {
		const primary = calendars.find((c) => c.primary);
		if (primary) return primary.id;
		if (calendars.length === 1) return calendars[0].id;
		return "";
	}, [calendars]);

	const [selectedAccountId, setSelectedAccountId] = useState<string>(defaultAccountId);
	const [selectedCalendarId, setSelectedCalendarId] = useState<string>(defaultCalendarId);

	useEffect(() => {
		if (defaultAccountId && !selectedAccountId) setSelectedAccountId(defaultAccountId);
	}, [defaultAccountId, selectedAccountId]);

	useEffect(() => {
		if (defaultCalendarId && !selectedCalendarId) setSelectedCalendarId(defaultCalendarId);
	}, [defaultCalendarId, selectedCalendarId]);

	const reviewConfig = interruptData.review_configs[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	const canApprove =
		!!selectedAccountId &&
		!!selectedCalendarId &&
		!!(pendingEdits?.summary ?? args.summary)?.trim();

	const handleApprove = useCallback(() => {
		if (phase !== "pending" || isPanelOpen || !canApprove) return;
		if (!allowedDecisions.includes("approve")) return;
		const isEdited = pendingEdits !== null;
		setWasEdited(isEdited);
		setProcessing();

		const finalArgs: Record<string, unknown> = {
			...args,
			connector_id: selectedAccountId ? Number(selectedAccountId) : null,
			calendar_id: selectedCalendarId || null,
		};

		if (pendingEdits) {
			finalArgs.summary = pendingEdits.summary;
			finalArgs.description = pendingEdits.description;
			if (pendingEdits.start_datetime) finalArgs.start_datetime = pendingEdits.start_datetime;
			if (pendingEdits.end_datetime) finalArgs.end_datetime = pendingEdits.end_datetime;
			if (pendingEdits.location !== undefined) finalArgs.location = pendingEdits.location;
			if (pendingEdits.attendees !== undefined) {
				finalArgs.attendees = pendingEdits.attendees
					.split(",")
					.map((e) => e.trim())
					.filter(Boolean);
			}
		}

		onDecision({
			type: isEdited ? "edit" : "approve",
			edited_action: {
				name: interruptData.action_requests[0].name,
				args: finalArgs,
			},
		});
	}, [
		phase,
		isPanelOpen,
		canApprove,
		allowedDecisions,
		setProcessing,
		onDecision,
		interruptData,
		args,
		selectedAccountId,
		selectedCalendarId,
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

	const attendeesList = (args.attendees as string[]) ?? [];
	const displayAttendees = pendingEdits?.attendees
		? pendingEdits.attendees
				.split(",")
				.map((e) => e.trim())
				.filter(Boolean)
		: attendeesList;

	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 transition-[box-shadow] duration-300">
			{/* Header */}
			<div className="flex items-start justify-between px-5 pt-5 pb-4 select-none">
				<div className="flex items-center gap-2">
					<div>
						<p className="text-sm font-semibold text-foreground">
							{phase === "rejected"
								? "Calendar Event Rejected"
								: phase === "processing" || phase === "complete"
									? "Calendar Event Approved"
									: "Create Calendar Event"}
						</p>
						{phase === "processing" ? (
							<TextShimmerLoader
								text={wasEdited ? "Creating event with your changes" : "Creating event"}
								size="sm"
							/>
						) : phase === "complete" ? (
							<p className="text-xs text-muted-foreground mt-0.5">
								{wasEdited ? "Event created with your changes" : "Event created"}
							</p>
						) : phase === "rejected" ? (
							<p className="text-xs text-muted-foreground mt-0.5">Event creation was cancelled</p>
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
							const extraFields: ExtraField[] = [
								{
									key: "start_datetime",
									label: "Start",
									type: "datetime-local",
									value: pendingEdits?.start_datetime ?? args.start_datetime ?? "",
								},
								{
									key: "end_datetime",
									label: "End",
									type: "datetime-local",
									value: pendingEdits?.end_datetime ?? args.end_datetime ?? "",
								},
								{
									key: "location",
									label: "Location",
									type: "text",
									value: pendingEdits?.location ?? args.location ?? "",
								},
								{
									key: "attendees",
									label: "Attendees",
									type: "emails",
									value: pendingEdits?.attendees ?? attendeesList.join(", "),
								},
							];
							openHitlEditPanel({
								title: pendingEdits?.summary ?? args.summary ?? "",
								content: pendingEdits?.description ?? args.description ?? "",
								toolName: "Calendar Event",
								extraFields,
								onSave: (newTitle, newContent, extraFieldValues) => {
									setIsPanelOpen(false);
									const extras = extraFieldValues ?? {};
									setPendingEdits({
										summary: newTitle,
										description: newContent,
										start_datetime:
											extras.start_datetime ??
											pendingEdits?.start_datetime ??
											args.start_datetime ??
											"",
										end_datetime:
											extras.end_datetime ?? pendingEdits?.end_datetime ?? args.end_datetime ?? "",
										location: extras.location ?? pendingEdits?.location ?? args.location ?? "",
										attendees:
											extras.attendees ?? pendingEdits?.attendees ?? attendeesList.join(", "),
									});
								},
								onClose: () => setIsPanelOpen(false),
							});
						}}
					>
						<Pencil className="size-3.5" />
						Edit
					</Button>
				)}
			</div>

			{/* Context section - pending with real dropdowns */}
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
											Google Calendar Account <span className="text-destructive">*</span>
										</p>
										<Select value={selectedAccountId} onValueChange={setSelectedAccountId}>
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

								{calendars.length > 0 && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">
											Calendar <span className="text-destructive">*</span>
										</p>
										<Select value={selectedCalendarId} onValueChange={setSelectedCalendarId}>
											<SelectTrigger className="w-full">
												<SelectValue placeholder="Select a calendar" />
											</SelectTrigger>
											<SelectContent>
												{calendars.map((cal) => (
													<SelectItem key={cal.id} value={cal.id}>
														{cal.summary}
														{cal.primary ? " (primary)" : ""}
													</SelectItem>
												))}
											</SelectContent>
										</Select>
									</div>
								)}

								{timezone && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">Timezone</p>
										<div className="flex items-center gap-2 w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm">
											<GlobeIcon className="size-3.5 text-muted-foreground shrink-0" />
											{timezone}
										</div>
									</div>
								)}
							</>
						)}
					</div>
				</>
			)}

			{/* Content preview - visible in ALL phases */}
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 pt-3 pb-3 space-y-2">
				{(pendingEdits?.summary ?? args.summary) && (
					<p className="text-sm font-medium text-foreground">
						{pendingEdits?.summary ?? args.summary}
					</p>
				)}

				{((pendingEdits?.start_datetime ?? args.start_datetime) ||
					(pendingEdits?.end_datetime ?? args.end_datetime)) && (
					<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
						<ClockIcon className="size-3.5 shrink-0" />
						<span>
							{(pendingEdits?.start_datetime ?? args.start_datetime)
								? formatDateTime(pendingEdits?.start_datetime ?? args.start_datetime)
								: ""}
							{(pendingEdits?.start_datetime ?? args.start_datetime) &&
							(pendingEdits?.end_datetime ?? args.end_datetime)
								? " — "
								: ""}
							{(pendingEdits?.end_datetime ?? args.end_datetime)
								? formatDateTime(pendingEdits?.end_datetime ?? args.end_datetime)
								: ""}
						</span>
					</div>
				)}

				{(pendingEdits?.location ?? args.location) && (
					<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
						<MapPinIcon className="size-3.5 shrink-0" />
						<span>{pendingEdits?.location ?? args.location}</span>
					</div>
				)}

				{displayAttendees.length > 0 && (
					<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
						<UsersIcon className="size-3.5 shrink-0" />
						<span>{displayAttendees.join(", ")}</span>
					</div>
				)}

				{(pendingEdits?.description ?? args.description) && (
					<div
						className="mt-2 max-h-[7rem] overflow-hidden text-sm"
						style={{
							maskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
							WebkitMaskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
						}}
					>
						<PlateEditor
							markdown={String(pendingEdits?.description ?? args.description)}
							readOnly
							preset="readonly"
							editorVariant="none"
							className="h-auto [&_[data-slate-editor]]:!min-h-0 [&_[data-slate-editor]>*:first-child]:!mt-0"
						/>
					</div>
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

function ErrorCard({ result }: { result: ErrorResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">Failed to create calendar event</p>
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

function SuccessCard({ result }: { result: SuccessResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-foreground">
					{result.message || "Calendar event created successfully"}
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

export const CreateCalendarEventToolUI = ({
	args,
	result,
}: ToolCallMessagePartProps<
	{
		summary: string;
		start_datetime: string;
		end_datetime: string;
		description?: string;
		location?: string;
		attendees?: string[];
	},
	CreateCalendarEventResult
>) => {
	const { dispatch } = useHitlDecision();

	if (!result) return null;

	if (isInterruptResult(result)) {
		return (
			<ApprovalCard
				args={args}
				interruptData={result as InterruptResult<CalendarCreateEventContext>}
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
	if (isInsufficientPermissionsResult(result))
		return <InsufficientPermissionsCard result={result} />;
	if (isErrorResult(result)) return <ErrorCard result={result} />;

	return <SuccessCard result={result as SuccessResult} />;
};
