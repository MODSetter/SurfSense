"use client";
import { useAtomValue } from "jotai";
import { AlertCircle, CalendarClock, Clock, Pencil, Save, Trash2 } from "lucide-react";
import { useState } from "react";
import { updateTriggerMutationAtom } from "@/atoms/automations/automations-mutation.atoms";
import { JsonView } from "@/components/json-view";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { type Trigger, triggerUpdateRequest } from "@/contracts/types/automation.types";
import { describeCron } from "@/lib/automations/describe-cron";
import { formatRelativeDate, formatRelativeFutureDate } from "@/lib/format-date";
import { DeleteTriggerDialog } from "./delete-trigger-dialog";

interface TriggerCardProps {
	trigger: Trigger;
	automationId: number;
	canUpdate: boolean;
	canDelete: boolean;
}

interface TriggerDraft {
	params: Record<string, unknown>;
	static_inputs: Record<string, unknown>;
}

function draftFromTrigger(trigger: Trigger): TriggerDraft {
	return {
		params: trigger.params,
		static_inputs: trigger.static_inputs ?? {},
	};
}

/**
 * One trigger row in the Triggers section of the detail page. Renders:
 *   - type icon + human-readable schedule + timezone
 *   - last_fired_at / next_fire_at hints
 *   - static_inputs as formatted JSON (when present)
 *   - enable toggle + remove button + inline edit (each gated independently)
 *
 * Inline edit covers ``params`` and ``static_inputs`` — the two fields the
 * backend ``PATCH /triggers/[id]`` endpoint accepts beyond ``enabled``.
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
	const tz = typeof trigger.params.timezone === "string" ? trigger.params.timezone : "UTC";
	const human = cron ? describeCron(cron) : trigger.type;
	const triggerLabel = cron ? `${human} · ${tz}` : trigger.type;
	const hasStaticInputs = Object.keys(trigger.static_inputs ?? {}).length > 0;

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
		const result = triggerUpdateRequest.safeParse(draft);
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
			<div className="rounded-md border border-border/60 overflow-hidden">
				<div className="flex items-center justify-between gap-4 px-4 py-3 border-b border-border/60">
					<div className="flex items-center gap-3 min-w-0">
						<CalendarClock className="h-4 w-4 text-muted-foreground shrink-0" aria-hidden />
						<div className="min-w-0">
							<div className="flex items-center gap-2 text-sm">
								<span className="font-medium text-foreground">{human}</span>
								<span className="text-muted-foreground">· {tz}</span>
							</div>
							{cron && <code className="text-xs font-mono text-muted-foreground">{cron}</code>}
						</div>
					</div>

					<div className="flex items-center gap-2 shrink-0">
						{canUpdate && (
							<div className="flex items-center gap-2">
								<span className="text-xs text-muted-foreground">
									{trigger.enabled ? "Enabled" : "Off"}
								</span>
								<Switch
									checked={trigger.enabled}
									onCheckedChange={handleToggle}
									disabled={updating || isEditing}
									aria-label={trigger.enabled ? "Disable trigger" : "Enable trigger"}
								/>
							</div>
						)}
						{canUpdate && !isEditing && (
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8 text-muted-foreground"
								onClick={startEdit}
								aria-label="Edit trigger"
							>
								<Pencil className="h-4 w-4" />
							</Button>
						)}
						{canDelete && (
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8 text-muted-foreground hover:text-destructive"
								onClick={() => setDeleteOpen(true)}
								disabled={isEditing}
								aria-label="Remove trigger"
							>
								<Trash2 className="h-4 w-4" />
							</Button>
						)}
					</div>
				</div>

				<div className="px-4 py-3 space-y-3 text-xs">
					{isEditing ? (
						<>
							<div className="rounded-md border border-input bg-background px-3 py-2 max-h-[24rem] overflow-auto">
								<JsonView
									src={draft}
									editable
									onChange={(next) => setDraft(next as TriggerDraft)}
									collapsed={false}
								/>
							</div>

							{issues.length > 0 && (
								<div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2">
									<div className="flex items-center gap-1.5 font-medium text-destructive mb-1">
										<AlertCircle className="h-3 w-3" aria-hidden />
										{issues.length === 1 ? "1 issue" : `${issues.length} issues`}
									</div>
									<ul className="space-y-0.5 text-destructive list-disc list-inside">
										{issues.map((issue) => (
											<li key={issue}>{issue}</li>
										))}
									</ul>
								</div>
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
								<Button type="button" size="sm" onClick={saveEdit} disabled={updating}>
									{updating ? (
										<Spinner size="xs" className="mr-1.5" />
									) : (
										<Save className="mr-1.5 h-3.5 w-3.5" />
									)}
									Save
								</Button>
							</div>
						</>
					) : (
						<>
							{(trigger.last_fired_at || trigger.next_fire_at) && (
								<dl className="grid grid-cols-[auto_minmax(0,1fr)] items-baseline gap-x-3 gap-y-1">
									{trigger.next_fire_at && (
										<TimeRow
											label="Next fire"
											iso={trigger.next_fire_at}
											tense="future"
											highlight={trigger.enabled}
										/>
									)}
									{trigger.last_fired_at && (
										<TimeRow label="Last fired" iso={trigger.last_fired_at} tense="past" />
									)}
								</dl>
							)}

							{hasStaticInputs && (
								<div>
									<div className="text-muted-foreground mb-1">Static inputs</div>
									<div className="rounded-md bg-muted/40 px-3 py-2 overflow-auto">
										<JsonView src={trigger.static_inputs} collapsed={1} />
									</div>
								</div>
							)}
						</>
					)}
				</div>
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

function TimeRow({
	label,
	iso,
	tense,
	highlight = false,
}: {
	label: string;
	iso: string;
	tense: "past" | "future";
	highlight?: boolean;
}) {
	const formatted = tense === "future" ? formatRelativeFutureDate(iso) : formatRelativeDate(iso);
	return (
		<>
			<dt className="text-muted-foreground inline-flex items-center gap-1.5 whitespace-nowrap">
				<Clock className="h-3 w-3" aria-hidden />
				{label}
			</dt>
			<dd
				className={
					highlight
						? "text-foreground font-medium min-w-0 truncate"
						: "text-muted-foreground min-w-0 truncate"
				}
				title={new Date(iso).toLocaleString()}
			>
				{formatted}
			</dd>
		</>
	);
}
