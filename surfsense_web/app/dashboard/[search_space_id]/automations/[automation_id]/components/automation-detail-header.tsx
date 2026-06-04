"use client";
import { useAtomValue } from "jotai";
import { ArrowLeft, Pause, Pencil, Play, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { updateAutomationMutationAtom } from "@/atoms/automations/automations-mutation.atoms";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type { Automation } from "@/contracts/types/automation.types";
import { DeleteAutomationDialog } from "../../components/delete-automation-dialog";

interface AutomationDetailHeaderProps {
	automation: Automation;
	searchSpaceId: number;
	canUpdate: boolean;
	canDelete: boolean;
}

/**
 * Title bar for the detail page: back link, name, status badge,
 * description, and the two destructive-ish primary actions (pause /
 * resume + delete). Same mutation atoms as the list-row actions to
 * keep caches coherent.
 *
 * Archived automations hide the pause/resume toggle (we don't unarchive
 * here — that flow comes later if we need it).
 */
export function AutomationDetailHeader({
	automation,
	searchSpaceId,
	canUpdate,
	canDelete,
}: AutomationDetailHeaderProps) {
	const router = useRouter();
	const { mutateAsync: updateAutomation, isPending: updating } = useAtomValue(
		updateAutomationMutationAtom
	);
	const [deleteOpen, setDeleteOpen] = useState(false);

	const canToggle = canUpdate && automation.status !== "archived";
	const nextStatus = automation.status === "active" ? "paused" : "active";
	const pauseLabel = automation.status === "active" ? "Pause" : "Resume";
	const PauseIcon = automation.status === "active" ? Pause : Play;

	const handleDeleted = useCallback(() => {
		router.push(`/dashboard/${searchSpaceId}/automations`);
	}, [router, searchSpaceId]);

	async function handleTogglePause() {
		await updateAutomation({
			automationId: automation.id,
			patch: { status: nextStatus },
		});
	}

	return (
		<>
			<div className="space-y-3">
				<Button asChild variant="ghost" size="sm" className="-ml-2 h-auto px-2 py-1">
					<Link
						href={`/dashboard/${searchSpaceId}/automations`}
						className="text-xs text-muted-foreground"
					>
						<ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
						Back to automations
					</Link>
				</Button>

				<div className="flex items-start justify-between gap-4 flex-wrap">
					<div className="space-y-2 min-w-0 flex-1">
						<h1 className="text-xl md:text-2xl font-semibold text-foreground break-words">
							{automation.name}
						</h1>
						{automation.description && (
							<p className="text-sm text-muted-foreground max-w-3xl">{automation.description}</p>
						)}
					</div>

					<div className="flex items-center gap-2 shrink-0">
						{canUpdate && (
							<Button
								asChild
								type="button"
								variant="ghost"
								size="sm"
								className="justify-start rounded-md bg-muted px-3 hover:bg-accent"
							>
								<Link href={`/dashboard/${searchSpaceId}/automations/${automation.id}/edit`}>
									<Pencil className="mr-1 h-4 w-4" />
									Edit
								</Link>
							</Button>
						)}
						{canToggle && (
							<Button
								type="button"
								variant="ghost"
								size="sm"
								onClick={handleTogglePause}
								disabled={updating}
								className="relative justify-start rounded-md bg-muted px-3 hover:bg-accent"
							>
								<span className={updating ? "inline-flex items-center whitespace-nowrap opacity-0" : "inline-flex items-center whitespace-nowrap"}>
									<PauseIcon className="mr-1 h-4 w-4" />
									{pauseLabel}
								</span>
								{updating && (
									<Spinner size="xs" className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2" />
								)}
							</Button>
						)}
						{canDelete && (
							<Button
								type="button"
								variant="ghost"
								size="sm"
								onClick={() => setDeleteOpen(true)}
								className="justify-start rounded-md bg-muted px-3 hover:bg-accent"
							>
								<Trash2 className="mr-1 h-4 w-4" />
								Delete
							</Button>
						)}
					</div>
				</div>
			</div>

			{canDelete && (
				<DeleteAutomationDialog
					open={deleteOpen}
					onOpenChange={setDeleteOpen}
					automationId={automation.id}
					automationName={automation.name}
					searchSpaceId={searchSpaceId}
					onDeleted={handleDeleted}
				/>
			)}
		</>
	);
}
