"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
	CalendarX2Icon,
	CalendarIcon,
	ClockIcon,
	MapPinIcon,
	CornerDownLeftIcon,
	TriangleAlertIcon,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";

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
	__decided__?: "approve" | "reject";
	action_requests: Array<{
		name: string;
		args: Record<string, unknown>;
	}>;
	review_configs: Array<{
		action_name: string;
		allowed_decisions: Array<"approve" | "reject">;
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
	message?: string;
	deleted_from_kb?: boolean;
}

interface ErrorResult {
	status: "error";
	message: string;
}

interface NotFoundResult {
	status: "not_found";
	message: string;
}

interface WarningResult {
	status: "success";
	warning: string;
	event_id?: string;
	message?: string;
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

type DeleteCalendarEventResult =
	| InterruptResult
	| SuccessResult
	| ErrorResult
	| NotFoundResult
	| WarningResult
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

function isWarningResult(result: unknown): result is WarningResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as WarningResult).status === "success" &&
		"warning" in result &&
		typeof (result as WarningResult).warning === "string"
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
		type: "approve" | "reject";
		message?: string;
		edited_action?: { name: string; args: Record<string, unknown> };
	}) => void;
}) {
	const [decided, setDecided] = useState<"approve" | "reject" | null>(
		interruptData.__decided__ ?? null
	);
	const wasAlreadyDecided = interruptData.__decided__ != null;
	const [deleteFromKb, setDeleteFromKb] = useState(false);

	const context = interruptData.context;
	const account = context?.account;
	const event = context?.event;

	const handleApprove = useCallback(() => {
		if (decided) return;
		setDecided("approve");
		onDecision({
			type: "approve",
			edited_action: {
				name: interruptData.action_requests[0].name,
				args: {
					event_id: event?.event_id,
					connector_id: account?.id,
					delete_from_kb: deleteFromKb,
				},
			},
		});
	}, [decided, onDecision, interruptData, event?.event_id, account?.id, deleteFromKb]);

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
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 transition-all duration-300">
			{/* Header */}
			<div className="flex items-start justify-between px-5 pt-5 pb-4 select-none">
				<div className="flex items-center gap-2">
					<CalendarX2Icon className="size-4 text-muted-foreground shrink-0" />
					<div>
						<p className="text-sm font-semibold text-foreground">
							{decided === "reject"
								? "Calendar Event Deletion Rejected"
								: decided === "approve"
									? "Calendar Event Deletion Approved"
									: "Delete Calendar Event"}
						</p>
						{decided === "approve" ? (
							wasAlreadyDecided ? (
								<p className="text-xs text-muted-foreground mt-0.5">Event deleted</p>
							) : (
								<TextShimmerLoader text="Deleting event" size="sm" />
							)
						) : (
							<p className="text-xs text-muted-foreground mt-0.5">
								{decided === "reject"
									? "Event deletion was cancelled"
									: "Requires your approval to proceed"}
							</p>
						)}
					</div>
				</div>
			</div>

			{/* Context section */}
			{!decided && context && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 space-y-4 select-none">
						{context.error ? (
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
										<p className="text-xs font-medium text-muted-foreground">Event to Delete</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm space-y-1.5">
											<div className="flex items-center gap-1.5">
												<CalendarIcon className="size-3 shrink-0 text-muted-foreground" />
												<span className="font-medium">{event.summary}</span>
											</div>
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
										</div>
									</div>
								)}
							</>
						)}
					</div>
				</>
			)}

			{/* delete_from_kb toggle */}
			{!decided && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 select-none">
						<div className="flex items-center gap-2.5">
							<Checkbox
								id="calendar-delete-from-kb"
								checked={deleteFromKb}
								onCheckedChange={(v) => setDeleteFromKb(v === true)}
								className="shrink-0"
							/>
							<label htmlFor="calendar-delete-from-kb" className="flex-1 cursor-pointer">
								<span className="text-sm text-foreground">Also remove from knowledge base</span>
								<p className="text-xs text-muted-foreground mt-0.5">
									This will permanently delete the event from your knowledge base (cannot be undone)
								</p>
							</label>
						</div>
					</div>
				</>
			)}

			{/* Action buttons */}
			{!decided && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 flex items-center gap-2 select-none">
						<Button
							size="sm"
							className="rounded-lg gap-1.5"
							onClick={handleApprove}
						>
							Approve
							<CornerDownLeftIcon className="size-3 opacity-60" />
						</Button>
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
				<p className="text-sm font-semibold text-destructive">Failed to delete calendar event</p>
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

function WarningCard({ result }: { result: WarningResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="flex items-start gap-3 border-b px-5 py-4">
				<TriangleAlertIcon className="size-4 mt-0.5 shrink-0 text-amber-500" />
				<p className="text-sm font-medium text-amber-600 dark:text-amber-500">Partial success</p>
			</div>
			<div className="px-5 py-4 space-y-2 text-xs">
				<p className="text-sm text-muted-foreground">{result.warning}</p>
			</div>
		</div>
	);
}

function SuccessCard({ result }: { result: SuccessResult }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-foreground">
					{result.message || "Calendar event deleted successfully"}
				</p>
			</div>
			{result.deleted_from_kb && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 text-xs">
						<span className="text-green-600 dark:text-green-500">
							Also removed from knowledge base
						</span>
					</div>
				</>
			)}
		</div>
	);
}

export const DeleteCalendarEventToolUI = makeAssistantToolUI<
	{ event_ref: string; delete_from_kb?: boolean },
	DeleteCalendarEventResult
>({
	toolName: "delete_calendar_event",
	render: function DeleteCalendarEventUI({ result }) {
		if (!result) return null;

		if (isInterruptResult(result)) {
			return (
				<ApprovalCard
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

		if (isNotFoundResult(result)) return <NotFoundCard result={result} />;
		if (isWarningResult(result)) return <WarningCard result={result} />;
		if (isAuthErrorResult(result)) return <AuthErrorCard result={result} />;
		if (isInsufficientPermissionsResult(result))
			return <InsufficientPermissionsCard result={result} />;
		if (isErrorResult(result)) return <ErrorCard result={result} />;

		return <SuccessCard result={result as SuccessResult} />;
	},
});
