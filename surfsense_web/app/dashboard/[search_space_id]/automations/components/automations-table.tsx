"use client";
import { CalendarDays, Info, Workflow } from "lucide-react";
import { Table, TableBody, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { AutomationSummary } from "@/contracts/types/automation.types";
import { AutomationRow } from "./automation-row";
import { AutomationsLoadingRows } from "./automations-loading";

interface AutomationsTableProps {
	automations: AutomationSummary[];
	searchSpaceId: number;
	loading: boolean;
	canUpdate: boolean;
	canDelete: boolean;
}

/**
 * Table shell + header. Rows render below — loading state renders skeleton
 * rows in the same shell so the layout doesn't shift on data arrival.
 */
export function AutomationsTable({
	automations,
	searchSpaceId,
	loading,
	canUpdate,
	canDelete,
}: AutomationsTableProps) {
	return (
		<div className="rounded-lg border border-border/60 bg-accent overflow-hidden">
			<Table className="table-fixed w-full">
				<TableHeader>
					<TableRow className="hover:bg-transparent border-b border-border/60">
						<TableHead className="px-4 md:px-6 border-r border-border/60">
							<span className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground/70">
								<Workflow size={14} className="opacity-60 text-muted-foreground" />
								Name
							</span>
						</TableHead>
						<TableHead className="border-r border-border/60 w-32">
							<span className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground/70">
								<Info size={14} className="opacity-60 text-muted-foreground" />
								Status
							</span>
						</TableHead>
						<TableHead className="hidden md:table-cell border-r border-border/60 w-40">
							<span className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground/70">
								<CalendarDays size={14} className="opacity-60 text-muted-foreground" />
								Updated
							</span>
						</TableHead>
						<TableHead className="px-4 md:px-6 w-16">
							<span className="sr-only">Actions</span>
						</TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{loading ? (
						<AutomationsLoadingRows />
					) : (
						automations.map((automation) => (
							<AutomationRow
								key={automation.id}
								automation={automation}
								searchSpaceId={searchSpaceId}
								canUpdate={canUpdate}
								canDelete={canDelete}
							/>
						))
					)}
				</TableBody>
			</Table>
		</div>
	);
}
