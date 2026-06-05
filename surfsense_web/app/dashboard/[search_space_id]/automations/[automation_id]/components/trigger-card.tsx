"use client";
import { useAtomValue } from "jotai";
import { AlertCircle, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { updateTriggerMutationAtom } from "@/atoms/automations/automations-mutation.atoms";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { type Trigger, triggerUpdateRequest } from "@/contracts/types/automation.types";
import { describeCron } from "@/lib/automations/describe-cron";
import { formatRelativeFutureDate } from "@/lib/format-date";
import {
	DEFAULT_SCHEDULE,
	fromCron,
	type ScheduleFrequency,
	toCron,
} from "@/lib/automations/schedule-builder";
import { TimezoneCombobox } from "../../components/builder/timezone-combobox";
import { DeleteTriggerDialog } from "./delete-trigger-dialog";

interface TriggerCardProps {
	trigger: Trigger;
	automationId: number;
	canUpdate: boolean;
	canDelete: boolean;
}

type SimpleFrequency = Extract<ScheduleFrequency, "hourly" | "daily" | "weekdays"> | "custom";

interface TriggerDraft {
	frequency: SimpleFrequency;
	hour: number;
	minute: number;
	timezone: string;
	cron: string;
}

const SIMPLE_FREQUENCIES = new Set<ScheduleFrequency>(["hourly", "daily", "weekdays"]);

function draftFromTrigger(trigger: Trigger): TriggerDraft {
	const cron = typeof trigger.params.cron === "string" ? trigger.params.cron : "";
	const timezone = typeof trigger.params.timezone === "string" ? trigger.params.timezone : "UTC";
	const model = fromCron(cron);
	if (model && SIMPLE_FREQUENCIES.has(model.frequency)) {
		return {
			frequency: model.frequency as SimpleFrequency,
			hour: model.hour,
			minute: model.minute,
			timezone,
			cron,
		};
	}
	return {
		frequency: "custom",
		hour: DEFAULT_SCHEDULE.hour,
		minute: DEFAULT_SCHEDULE.minute,
		timezone,
		cron,
	};
}

function pad(value: number): string {
	return value.toString().padStart(2, "0");
}

function clampInt(raw: string, min: number, max: number): number {
	const value = Number.parseInt(raw, 10);
	if (Number.isNaN(value)) return min;
	return Math.min(max, Math.max(min, value));
}

/**
 * One trigger row in the Triggers section of the detail page. Renders:
 *   - human-readable schedule
 *   - compact enable toggle
 *   - dropdown actions for edit/remove
 *
 * Inline edit keeps schedule editing intentionally small: common frequencies,
 * time, timezone, and raw cron only for schedules outside the simple model.
 * ``enabled`` stays on the Switch so the two surfaces don't fight.
 */
export function TriggerCard({ trigger, automationId, canUpdate, canDelete }: TriggerCardProps) {
	const { mutateAsync: updateTrigger, isPending: updating } =
		useAtomValue(updateTriggerMutationAtom);
	const [deleteOpen, setDeleteOpen] = useState(false);
	const [isEditing, setIsEditing] = useState(false);
	const [draft, setDraft] = useState<TriggerDraft>(() => draftFromTrigger(trigger));
	const [issues, setIssues] = useState<string[]>([]);

	const cron = typeof trigger.params.cron === "string" ? trigger.params.cron : undefined;
	const human = cron ? describeCron(cron) : trigger.type;
	const triggerLabel = human;
	const showActions = (canUpdate && !isEditing) || canDelete;

	async function handleToggle(checked: boolean) {
		await updateTrigger({
			automationId,
			triggerId: trigger.id,
			patch: { enabled: checked },
		});
	}

	function startEdit() {
		setDraft(draftFromTrigger(trigger));
		setIssues([]);
		setIsEditing(true);
	}

	function cancelEdit() {
		setIsEditing(false);
		setIssues([]);
	}

	async function saveEdit() {
		setIssues([]);
		const params =
			draft.frequency === "custom"
				? { cron: draft.cron.trim(), timezone: draft.timezone }
				: {
						cron: toCron({
							...DEFAULT_SCHEDULE,
							frequency: draft.frequency,
							hour: draft.hour,
							minute: draft.minute,
						}),
						timezone: draft.timezone,
					};
		const result = triggerUpdateRequest.safeParse({
			params,
			static_inputs: trigger.static_inputs ?? {},
		});
		if (!result.success) {
			setIssues(
				result.error.issues.map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`)
			);
			return;
		}
		try {
			await updateTrigger({
				automationId,
				triggerId: trigger.id,
				patch: result.data,
			});
			setIsEditing(false);
		} catch (err) {
			setIssues([(err as Error).message ?? "Update failed"]);
		}
	}

	return (
		<>
			<div className="rounded-md border border-border/60 bg-background/30">
				<div className="flex items-center justify-between gap-3 px-4 py-3">
					<div className="min-w-0 truncate text-sm font-medium text-foreground">{human}</div>

					<div className="flex shrink-0 items-center gap-2">
						{canUpdate && (
							<Switch
								checked={trigger.enabled}
								onCheckedChange={handleToggle}
								disabled={updating || isEditing}
								aria-label={trigger.enabled ? "Disable trigger" : "Enable trigger"}
								className="h-5 w-9 [&>span]:h-4 [&>span]:w-4 [&>span[data-state=checked]]:translate-x-4"
							/>
						)}
						{showActions && (
							<DropdownMenu>
								<DropdownMenuTrigger asChild>
									<Button
										variant="ghost"
										size="icon"
										className="h-6 w-6 hover:bg-transparent"
										disabled={isEditing}
										aria-label="Trigger actions"
									>
										<MoreHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
									</Button>
								</DropdownMenuTrigger>
								<DropdownMenuContent align="end" className="w-32 z-80">
									{canUpdate && !isEditing && (
										<DropdownMenuItem onSelect={startEdit}>
											<Pencil className="mr-2 h-4 w-4" />
											Edit
										</DropdownMenuItem>
									)}
									{canDelete && (
										<DropdownMenuItem onSelect={() => setDeleteOpen(true)}>
											<Trash2 className="mr-2 h-4 w-4" />
											Delete
										</DropdownMenuItem>
									)}
								</DropdownMenuContent>
							</DropdownMenu>
						)}
					</div>
				</div>

				{!isEditing && trigger.next_fire_at ? (
					<div className="flex items-center gap-3 border-t border-border/60 px-4 py-3 text-sm">
						<div className="inline-flex items-center gap-1.5 text-muted-foreground">
							<span>Next fire:</span>
						</div>
						<div
							className={
								trigger.enabled
									? "min-w-0 truncate font-medium text-foreground"
									: "min-w-0 truncate text-muted-foreground"
							}
							title={new Date(trigger.next_fire_at).toLocaleString()}
						>
							{formatRelativeFutureDate(trigger.next_fire_at)}
						</div>
					</div>
				) : null}

				{isEditing ? (
					<div className="space-y-3 border-t border-border/60 px-4 py-3 text-xs">
						<div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
							<div className="space-y-1.5">
								<label className="text-xs font-medium text-muted-foreground" htmlFor="trigger-runs">
									Runs
								</label>
								<Select
									value={draft.frequency}
									onValueChange={(value) =>
										setDraft((prev) => ({ ...prev, frequency: value as SimpleFrequency }))
									}
								>
									<SelectTrigger id="trigger-runs" className="w-full">
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										<SelectItem value="hourly">Every hour</SelectItem>
										<SelectItem value="daily">Daily</SelectItem>
										<SelectItem value="weekdays">Weekdays</SelectItem>
										<SelectItem value="custom">Custom cron</SelectItem>
									</SelectContent>
								</Select>
							</div>

							{draft.frequency === "hourly" ? (
								<div className="space-y-1.5">
									<label
										className="text-xs font-medium text-muted-foreground"
										htmlFor="trigger-minute"
									>
										At minute
									</label>
									<Input
										id="trigger-minute"
										type="number"
										min={0}
										max={59}
										value={draft.minute}
										onChange={(event) =>
											setDraft((prev) => ({
												...prev,
												minute: clampInt(event.target.value, 0, 59),
											}))
										}
									/>
								</div>
							) : draft.frequency !== "custom" ? (
								<div className="space-y-1.5">
									<label className="text-xs font-medium text-muted-foreground" htmlFor="trigger-time">
										Time
									</label>
									<Input
										id="trigger-time"
										type="time"
										value={`${pad(draft.hour)}:${pad(draft.minute)}`}
										onChange={(event) => {
											const [hour, minute] = event.target.value.split(":");
											setDraft((prev) => ({
												...prev,
												hour: clampInt(hour, 0, 23),
												minute: clampInt(minute, 0, 59),
											}));
										}}
									/>
								</div>
							) : (
								<div className="space-y-1.5">
									<label className="text-xs font-medium text-muted-foreground" htmlFor="trigger-cron">
										Schedule expression
									</label>
									<Input
										id="trigger-cron"
										value={draft.cron}
										placeholder="0 9 * * 1-5"
										className="font-mono"
										onChange={(event) =>
											setDraft((prev) => ({ ...prev, cron: event.target.value }))
										}
									/>
								</div>
							)}

							<div className="space-y-1.5 sm:col-span-2">
								<div className="text-xs font-medium text-muted-foreground">Timezone</div>
								<TimezoneCombobox
									value={draft.timezone}
									onChange={(timezone) => setDraft((prev) => ({ ...prev, timezone }))}
								/>
							</div>
						</div>

						{issues.length > 0 && (
							<Alert variant="destructive">
								<AlertCircle aria-hidden />
								<AlertTitle>
									{issues.length === 1 ? "1 issue" : `${issues.length} issues`}
								</AlertTitle>
								<AlertDescription>
									<ul className="list-inside list-disc">
										{issues.map((issue) => (
											<li key={issue}>{issue}</li>
										))}
									</ul>
								</AlertDescription>
							</Alert>
						)}

						<div className="flex items-center justify-end gap-2">
							<Button
								type="button"
								variant="ghost"
								size="sm"
								onClick={cancelEdit}
								disabled={updating}
							>
								Cancel
							</Button>
							<Button
								type="button"
								size="sm"
								onClick={saveEdit}
								disabled={updating}
								className="relative"
							>
								<span className={updating ? "opacity-0" : undefined}>Save</span>
								{updating ? (
									<Spinner
										size="xs"
										className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
									/>
								) : null}
							</Button>
						</div>
					</div>
				) : null}
			</div>

			{canDelete && (
				<DeleteTriggerDialog
					open={deleteOpen}
					onOpenChange={setDeleteOpen}
					automationId={automationId}
					triggerId={trigger.id}
					triggerLabel={triggerLabel}
				/>
			)}
		</>
	);
}
