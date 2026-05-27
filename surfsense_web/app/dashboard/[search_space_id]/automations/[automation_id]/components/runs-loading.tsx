"use client";
import { Skeleton } from "@/components/ui/skeleton";

const ROW_KEYS = ["a", "b", "c"] as const;

export function RunsLoading() {
	return (
		<div className="space-y-2">
			{ROW_KEYS.map((key) => (
				<div
					key={key}
					className="flex items-center justify-between gap-4 rounded-md border border-border/60 bg-background/50 px-4 py-3"
				>
					<div className="flex items-center gap-3">
						<Skeleton className="h-5 w-20 rounded-md" />
						<Skeleton className="h-3 w-32" />
					</div>
					<Skeleton className="h-3 w-16" />
				</div>
			))}
		</div>
	);
}
