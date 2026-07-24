"use client";
import { Skeleton } from "@/components/ui/skeleton";
import { TableCell, TableRow } from "@/components/ui/table";

const ROW_KEYS = ["sk-1", "sk-2", "sk-3"];

/**
 * Skeleton rows for the automations table. Number of rows is fixed since
 * we don't know the count ahead of time and three placeholders is enough
 * to communicate "loading" without flashing too much chrome.
 */
export function AutomationsLoadingRows() {
	return (
		<>
			{ROW_KEYS.map((key) => (
				<TableRow key={key} className="h-12 border-b border-border/60 hover:bg-transparent">
					<TableCell className="px-4 md:px-6 py-2.5 border-r border-border/60 align-middle">
						<Skeleton className="h-4 w-32 max-w-full md:w-40" />
					</TableCell>
					<TableCell className="px-4 py-2.5 border-r border-border/60 w-32 align-middle">
						<Skeleton className="h-5 w-16 rounded-md" />
					</TableCell>
					<TableCell className="hidden md:table-cell px-4 py-2.5 border-r border-border/60 w-40 align-middle">
						<Skeleton className="h-3 w-20" />
					</TableCell>
					<TableCell className="px-4 md:px-6 py-2.5 w-16 align-middle">
						<Skeleton className="h-7 w-7 rounded-md ml-auto" />
					</TableCell>
				</TableRow>
			))}
		</>
	);
}
