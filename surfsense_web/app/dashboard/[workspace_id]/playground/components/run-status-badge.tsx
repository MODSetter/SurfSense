import { Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";

/** Scraper runs: ``running`` (async, in-flight), ``success``, ``error``, ``cancelled``. */
export function RunStatusBadge({ status }: { status: string }) {
	const normalized = status.toLowerCase();
	if (normalized === "running") {
		return (
			<Badge variant="secondary" className="gap-1 bg-blue-500/15 text-blue-600 dark:text-blue-400">
				<Loader2 className="h-3 w-3 animate-spin" />
				Running
			</Badge>
		);
	}
	if (normalized === "success") {
		return (
			<Badge
				variant="secondary"
				className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
			>
				Success
			</Badge>
		);
	}
	if (normalized === "error") {
		return <Badge variant="destructive">Error</Badge>;
	}
	if (normalized === "cancelled") {
		return (
			<Badge variant="secondary" className="bg-amber-500/15 text-amber-600 dark:text-amber-400">
				Cancelled
			</Badge>
		);
	}
	return <Badge variant="outline">{status}</Badge>;
}
