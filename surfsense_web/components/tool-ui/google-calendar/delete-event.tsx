"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { CalendarIcon, ClockIcon, CornerDownLeftIcon, MapPinIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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

interface CalendarDeleteEventContext {
	account?: GoogleCalendarAccount;
	event?: CalendarEvent;
	error?: string;
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
	| InterruptResult<CalendarDeleteEventContext>
	| SuccessResult
	| ErrorResult
	| NotFoundResult
	| WarningResult
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
	interruptData: InterruptResult<CalendarDeleteEventContext>;
	onDecision: (decision: HitlDecision) => void;
}) {
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);
	const [deleteFromKb, setDeleteFromKb] = useState(false);

	const context = interruptData.context;
	const account = context?.account;
	const event = context?.event;

	const handleApprove = useCallback(() => {
		if (phase !== "pending") return;
		setProcessing();
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
	}, [phase, setProcessing, onDecision, interruptData, event?.event_id, account?.id, deleteFromKb]);

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
								? "Calendar Event Deletion Rejected"
								: phase === "processing" || phase === "complete"
									? "Calendar Event Deletion Approved"
									: "Delete Calendar Event"}
						</p>
						{phase === "processing" ? (
							<TextShimmerLoader text="Deleting event" size="sm" />
						) : phase === "complete" ? (
							<p className="text-xs text-muted-foreground mt-0.5">Event deleted</p>
						) : phase === "rejected" ? (
							<p className="text-xs text-muted-foreground mt-0.5">Event deletion was cancelled</p>
						) : (
							<p className="text-xs text-muted-foreground mt-0.5">
								Requires your approval to proceed
							</p>
						)}
					</div>
				</div>
			</div>

			{phase !== "rejected" && context && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 space-y-4 select-none">
						{context.error ? (
							<p className="text-sm text-destructive">{context.error}</p>
						) : (
							<>
								{account && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">
											Google Calendar Account
										</p>
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
			{phase === "pending" && (
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
			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 flex items-center gap-2 select-none">
						<Button size="sm" className="rounded-lg gap-1.5" onClick={handleApprove}>
							Approve
							<CornerDownLeftIcon className="size-3 opacity-60" />
						</Button>
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

export const DeleteCalendarEventToolUI = ({
	result,
}: ToolCallMessagePartProps<
	{ event_title_or_id: string; delete_from_kb?: boolean },
	DeleteCalendarEventResult
>) => {
	const { dispatch } = useHitlDecision();

	if (!result) return null;

	if (isInterruptResult(result)) {
		return (
			<ApprovalCard
				interruptData={result as InterruptResult<CalendarDeleteEventContext>}
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
	if (isWarningResult(result)) return <WarningCard result={result} />;
	if (isAuthErrorResult(result)) return <AuthErrorCard result={result} />;
	if (isInsufficientPermissionsResult(result))
		return <InsufficientPermissionsCard result={result} />;
	if (isErrorResult(result)) return <ErrorCard result={result} />;

	return <SuccessCard result={result as SuccessResult} />;
};
