"use client";
import { useAtomValue } from "jotai";
import { AlertCircle, MoreHorizontal, Pencil, Save, Trash2 } from "lucide-react";
import { useState } from "react";
import { updateTriggerMutationAtom } from "@/atoms/automations/automations-mutation.atoms";
import { JsonView } from "@/components/json-view";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { type Trigger, triggerUpdateRequest } from "@/contracts/types/automation.types";
import { describeCron } from "@/lib/automations/describe-cron";
import { formatRelativeFutureDate } from "@/lib/format-date";
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
 *   - human-readable schedule
 *   - compact enable toggle
 *   - dropdown actions for edit/remove
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
						<div className="rounded-md border border-input bg-background px-3 py-2 max-h-[24rem] overflow-auto">
							<JsonView
								src={draft}
								editable
								onChange={(next) => setDraft(next as TriggerDraft)}
								collapsed={false}
							/>
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
							<Button type="button" size="sm" onClick={saveEdit} disabled={updating}>
								{updating ? (
									<Spinner size="xs" className="mr-1.5" />
								) : (
									<Save className="mr-1.5 h-3.5 w-3.5" />
								)}
								Save
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
