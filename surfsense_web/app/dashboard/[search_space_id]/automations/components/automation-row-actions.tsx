"use client";
import { useAtomValue } from "jotai";
import { MoreHorizontal, Pause, Play, Trash2 } from "lucide-react";
import { useState } from "react";
import { updateAutomationMutationAtom } from "@/atoms/automations/automations-mutation.atoms";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { AutomationSummary } from "@/contracts/types/automation.types";
import { DeleteAutomationDialog } from "./delete-automation-dialog";

interface AutomationRowActionsProps {
	automation: AutomationSummary;
	searchSpaceId: number;
	canUpdate: boolean;
	canDelete: boolean;
}

/**
 * Three-dot menu on each row: pause/resume (if updatable) and delete
 * (if deletable). The menu itself is hidden when the user has neither
 * permission so we don't render an empty trigger.
 */
export function AutomationRowActions({
	automation,
	searchSpaceId,
	canUpdate,
	canDelete,
}: AutomationRowActionsProps) {
	const { mutateAsync: updateAutomation, isPending: updating } = useAtomValue(
		updateAutomationMutationAtom
	);
	const [deleteOpen, setDeleteOpen] = useState(false);

	if (!canUpdate && !canDelete) return null;

	const nextStatus = automation.status === "active" ? "paused" : "active";
	const pauseLabel = automation.status === "active" ? "Pause" : "Resume";
	const PauseIcon = automation.status === "active" ? Pause : Play;
	const canToggle = canUpdate && automation.status !== "archived";

	async function handleTogglePause() {
		await updateAutomation({
			automationId: automation.id,
			patch: { status: nextStatus },
		});
	}

	return (
		<>
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button
						variant="ghost"
						size="icon"
						className="h-8 w-8"
						aria-label={`Actions for ${automation.name}`}
					>
						<MoreHorizontal className="h-4 w-4" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end" className="w-40">
					{canToggle && (
						<DropdownMenuItem onSelect={handleTogglePause} disabled={updating}>
							<PauseIcon className="mr-2 h-4 w-4" />
							{pauseLabel}
						</DropdownMenuItem>
					)}
					{canToggle && canDelete && <DropdownMenuSeparator />}
					{canDelete && (
						<DropdownMenuItem
							onSelect={() => setDeleteOpen(true)}
							className="text-destructive focus:text-destructive"
						>
							<Trash2 className="mr-2 h-4 w-4" />
							Delete
						</DropdownMenuItem>
					)}
				</DropdownMenuContent>
			</DropdownMenu>

			{canDelete && (
				<DeleteAutomationDialog
					open={deleteOpen}
					onOpenChange={setDeleteOpen}
					automationId={automation.id}
					automationName={automation.name}
					searchSpaceId={searchSpaceId}
				/>
			)}
		</>
	);
}
