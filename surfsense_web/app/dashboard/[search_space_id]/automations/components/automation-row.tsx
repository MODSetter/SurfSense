"use client";
import Link from "next/link";
import { TableCell, TableRow } from "@/components/ui/table";
import type { AutomationSummary } from "@/contracts/types/automation.types";
import { formatRelativeDate } from "@/lib/format-date";
import { AutomationRowActions } from "./automation-row-actions";
import { AutomationStatusBadge } from "./automation-status-badge";

interface AutomationRowProps {
	automation: AutomationSummary;
	searchSpaceId: number;
	canUpdate: boolean;
	canDelete: boolean;
}

/**
 * One row in the automations table. The name links to the detail page;
 * actions are gated by ``canUpdate`` / ``canDelete``. Trigger summary
 * is intentionally left to the detail page — list responses don't
 * include triggers and we want to avoid N+1 detail fetches.
 */
export function AutomationRow({
	automation,
	searchSpaceId,
	canUpdate,
	canDelete,
}: AutomationRowProps) {
	return (
		<TableRow className="border-b border-border/60 hover:bg-muted/40">
			<TableCell className="px-4 md:px-6 py-3 border-r border-border/60">
				<div className="flex flex-col gap-0.5 min-w-0">
					<Link
						href={`/dashboard/${searchSpaceId}/automations/${automation.id}`}
						className="text-sm font-medium text-foreground hover:underline truncate"
					>
						{automation.name}
					</Link>
					{automation.description && (
						<span className="text-xs text-muted-foreground line-clamp-1">
							{automation.description}
						</span>
					)}
				</div>
			</TableCell>
			<TableCell className="px-4 py-3 border-r border-border/60 w-32">
				<AutomationStatusBadge status={automation.status} />
			</TableCell>
			<TableCell className="hidden md:table-cell px-4 py-3 border-r border-border/60 w-40 text-xs text-muted-foreground">
				{formatRelativeDate(automation.updated_at)}
			</TableCell>
			<TableCell className="px-4 md:px-6 py-3 w-16 text-right">
				<AutomationRowActions
					automation={automation}
					searchSpaceId={searchSpaceId}
					canUpdate={canUpdate}
					canDelete={canDelete}
				/>
			</TableCell>
		</TableRow>
	);
}
