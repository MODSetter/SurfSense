"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
	CalendarPlusIcon,
	ClockIcon,
	MapPinIcon,
	UsersIcon,
	GlobeIcon,
	CornerDownLeftIcon,
	Pen,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSetAtom } from "jotai";
import { Button } from "@/components/ui/button";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { PlateEditor } from "@/components/editor/plate-editor";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { openHitlEditPanelAtom } from "@/atoms/chat/hitl-edit-panel.atom";
import type { ExtraField } from "@/atoms/chat/hitl-edit-panel.atom";

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
		accounts?: GoogleCalendarAccount[];
		calendars?: CalendarEntry[];
		timezone?: string;
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
	| InterruptResult
	| SuccessResult
	| ErrorResult
	| InsufficientPermissionsResult
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
	const [isPanelOpen, setIsPanelOpen] = useState(false);
	const openHitlEditPanel = useSetAtom(openHitlEditPanelAtom);

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

	const reviewConfig = interruptData.review_configs[0];
	const allowedDecisions = reviewConfig?.allowed_decisions ?? ["approve", "reject"];
	const canEdit = allowedDecisions.includes("edit");

	const canApprove =
		!!selectedAccountId &&
		!!selectedCalendarId &&
		!!args.summary?.trim();

	const handleApprove = useCallback(() => {
		if (decided || isPanelOpen || !canApprove) return;
		if (!allowedDecisions.includes("approve")) return;
		setDecided("approve");
		onDecision({
			type: "approve",
			edited_action: {
				name: interruptData.action_requests[0].name,
				args: {
					...args,
					connector_id: selectedAccountId ? Number(selectedAccountId) : null,
					calendar_id: selectedCalendarId || null,
				},
			},
		});
	}, [decided, isPanelOpen, canApprove, allowedDecisions, onDecision, interruptData, args, selectedAccountId, selectedCalendarId]);

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

	const attendeesList = (args.attendees as string[]) ?? [];

	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 transition-all duration-300">
			{/* Header */}
			<div className="flex items-start justify-between px-5 pt-5 pb-4 select-none">
				<div className="flex items-center gap-2">
					<CalendarPlusIcon className="size-4 text-muted-foreground shrink-0" />
					<div>
						<p className="text-sm font-semibold text-foreground">
							{decided === "reject"
								? "Calendar Event Rejected"
								: decided === "approve" || decided === "edit"
									? "Calendar Event Approved"
									: "Create Calendar Event"}
						</p>
						<p className="text-xs text-muted-foreground mt-0.5">
							{decided === "reject"
								? "Event creation was cancelled"
								: decided === "edit"
									? "Event creation is in progress with your changes"
									: decided === "approve"
										? "Event creation is in progress"
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
							const extraFields: ExtraField[] = [
								{ key: "start_datetime", label: "Start", type: "datetime-local", value: args.start_datetime || "" },
								{ key: "end_datetime", label: "End", type: "datetime-local", value: args.end_datetime || "" },
								{ key: "location", label: "Location", type: "text", value: args.location || "" },
								{ key: "attendees", label: "Attendees (comma-separated emails)", type: "text", value: attendeesList.join(", ") },
							];
							openHitlEditPanel({
								title: args.summary ?? "",
								content: args.description ?? "",
								toolName: "Calendar Event",
								extraFields,
								onSave: (newTitle, newContent, extraFieldValues) => {
									setIsPanelOpen(false);
									setDecided("edit");

									const editedArgs: Record<string, unknown> = {
										...args,
										summary: newTitle,
										description: newContent,
										connector_id: selectedAccountId ? Number(selectedAccountId) : null,
										calendar_id: selectedCalendarId || null,
									};

									if (extraFieldValues) {
										if (extraFieldValues.start_datetime) editedArgs.start_datetime = extraFieldValues.start_datetime;
										if (extraFieldValues.end_datetime) editedArgs.end_datetime = extraFieldValues.end_datetime;
										if (extraFieldValues.location !== undefined) editedArgs.location = extraFieldValues.location;
										if (extraFieldValues.attendees !== undefined) {
											editedArgs.attendees = extraFieldValues.attendees
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
			{!decided && interruptData.context && (
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
														{cal.summary}{cal.primary ? " (primary)" : ""}
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

			{/* Content preview */}
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 pt-3 pb-3 space-y-2">
				{args.summary && (
					<p className="text-sm font-medium text-foreground">{args.summary}</p>
				)}

				{(args.start_datetime || args.end_datetime) && (
					<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
						<ClockIcon className="size-3.5 shrink-0" />
						<span>
							{args.start_datetime ? formatDateTime(args.start_datetime) : ""}
							{args.start_datetime && args.end_datetime ? " — " : ""}
							{args.end_datetime ? formatDateTime(args.end_datetime) : ""}
						</span>
					</div>
				)}

				{args.location && (
					<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
						<MapPinIcon className="size-3.5 shrink-0" />
						<span>{args.location}</span>
					</div>
				)}

				{attendeesList.length > 0 && (
					<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
						<UsersIcon className="size-3.5 shrink-0" />
						<span>{attendeesList.join(", ")}</span>
					</div>
				)}

				{args.description && (
					<div
						className="mt-2 max-h-[7rem] overflow-hidden text-sm"
						style={{
							maskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
							WebkitMaskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
						}}
					>
						<PlateEditor
							markdown={String(args.description)}
							readOnly
							preset="readonly"
							editorVariant="none"
							className="h-auto [&_[data-slate-editor]]:!min-h-0 [&_[data-slate-editor]>*:first-child]:!mt-0"
						/>
					</div>
				)}
			</div>

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
								disabled={!canApprove}
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

export const CreateCalendarEventToolUI = makeAssistantToolUI<
	{
		summary: string;
		start_datetime: string;
		end_datetime: string;
		description?: string;
		location?: string;
		attendees?: string[];
	},
	CreateCalendarEventResult
>({
	toolName: "create_calendar_event",
	render: function CreateCalendarEventUI({ args, result, status }) {
		if (status.type === "running") {
			return (
				<div className="my-4 max-w-lg rounded-2xl border bg-muted/30 px-5 py-4 select-none">
					<TextShimmerLoader text="Preparing calendar event..." size="sm" />
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

		if (isAuthErrorResult(result)) return <AuthErrorCard result={result} />;
		if (isInsufficientPermissionsResult(result))
			return <InsufficientPermissionsCard result={result} />;
		if (isErrorResult(result)) return <ErrorCard result={result} />;

		return <SuccessCard result={result as SuccessResult} />;
	},
});
