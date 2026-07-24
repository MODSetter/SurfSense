"use client";

import { XIcon } from "lucide-react";
import { useParams } from "next/navigation";
import type { FC } from "react";
import { RunDetail } from "@/app/dashboard/[workspace_id]/playground/components/run-detail";
import { Button } from "@/components/ui/button";

/** Right-panel viewer for a cited scraper run. `runId` is the `run_<uuid>` handle. */
export const RunCitationPanelContent: FC<{ runId: string; onClose?: () => void }> = ({
	runId,
	onClose,
}) => {
	const params = useParams();
	const rawWorkspaceId = Array.isArray(params?.workspace_id)
		? params.workspace_id[0]
		: params?.workspace_id;
	const workspaceId = Number(rawWorkspaceId);
	const scraperRunId = runId.replace(/^run_/, "");

	return (
		<>
			<div className="shrink-0 flex h-12 items-center justify-between px-3 border-b">
				<h2 className="select-none text-lg font-semibold">Scraper run</h2>
				{onClose && (
					<Button
						variant="ghost"
						size="icon"
						onClick={onClose}
						className="h-8 w-8 rounded-full shrink-0 text-muted-foreground hover:text-accent-foreground"
					>
						<XIcon className="h-4 w-4" />
						<span className="sr-only">Close run panel</span>
					</Button>
				)}
			</div>

			<div className="flex-1 overflow-y-auto">
				{Number.isFinite(workspaceId) ? (
					<RunDetail workspaceId={workspaceId} runId={scraperRunId} />
				) : (
					<p className="p-4 text-sm text-muted-foreground">Open a workspace to view this run.</p>
				)}
			</div>
		</>
	);
};
