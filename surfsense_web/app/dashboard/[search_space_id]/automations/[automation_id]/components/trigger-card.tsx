"use client";
import { useAtomValue } from "jotai";
import { CalendarClock, Clock, Trash2 } from "lucide-react";
import { useState } from "react";
import { updateTriggerMutationAtom } from "@/atoms/automations/automations-mutation.atoms";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import type { Trigger } from "@/contracts/types/automation.types";
import { formatRelativeDate } from "@/lib/format-date";
import { describeCron } from "../../lib/describe-cron";
import { DeleteTriggerDialog } from "./delete-trigger-dialog";

interface TriggerCardProps {
	trigger: Trigger;
	automationId: number;
	canUpdate: boolean;
	canDelete: boolean;
}

/**
 * One trigger row in the Triggers section of the detail page. Renders:
 *   - type icon + human-readable schedule + timezone
 *   - last_fired_at / next_fire_at hints
 *   - static_inputs as formatted JSON (when present)
 *   - enable toggle + remove button (each gated independently)
 *
 * Editing params (cron, timezone, static_inputs) lives behind the future
 * raw-JSON path; this card stays read-only-except-for-toggle for v1.
 */
export function TriggerCard({ trigger, automationId, canUpdate, canDelete }: TriggerCardProps) {
	const { mutateAsync: updateTrigger, isPending: updating } =
		useAtomValue(updateTriggerMutationAtom);
	const [deleteOpen, setDeleteOpen] = useState(false);

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

	return (
		<>
			<div className="rounded-md border border-border/60 bg-background overflow-hidden">
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
									disabled={updating}
									aria-label={trigger.enabled ? "Disable trigger" : "Enable trigger"}
								/>
							</div>
						)}
						{canDelete && (
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8 text-muted-foreground hover:text-destructive"
								onClick={() => setDeleteOpen(true)}
								aria-label="Remove trigger"
							>
								<Trash2 className="h-4 w-4" />
							</Button>
						)}
					</div>
				</div>

				<div className="px-4 py-3 space-y-3 text-xs">
					{(trigger.last_fired_at || trigger.next_fire_at) && (
						<dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5">
							{trigger.next_fire_at && (
								<TimeRow label="Next fire" iso={trigger.next_fire_at} highlight={trigger.enabled} />
							)}
							{trigger.last_fired_at && <TimeRow label="Last fired" iso={trigger.last_fired_at} />}
						</dl>
					)}

					{hasStaticInputs && (
						<div>
							<div className="text-muted-foreground mb-1">Static inputs</div>
							<pre className="rounded-md bg-muted/40 px-3 py-2 font-mono text-foreground overflow-x-auto whitespace-pre-wrap break-words">
								{JSON.stringify(trigger.static_inputs, null, 2)}
							</pre>
						</div>
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
	highlight = false,
}: {
	label: string;
	iso: string;
	highlight?: boolean;
}) {
	return (
		<div className="flex items-baseline gap-2 min-w-0">
			<dt className="text-muted-foreground shrink-0 inline-flex items-center gap-1">
				<Clock className="h-3 w-3" aria-hidden />
				{label}:
			</dt>
			<dd
				className={
					highlight
						? "text-foreground font-medium min-w-0 truncate"
						: "text-muted-foreground min-w-0 truncate"
				}
			>
				{formatRelativeDate(iso)}
			</dd>
		</div>
	);
}
