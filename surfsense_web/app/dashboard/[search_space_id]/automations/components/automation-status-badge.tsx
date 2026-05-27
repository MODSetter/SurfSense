"use client";
import { Archive, CircleDot, Pause } from "lucide-react";
import type { AutomationStatus } from "@/contracts/types/automation.types";
import { cn } from "@/lib/utils";

interface AutomationStatusBadgeProps {
	status: AutomationStatus;
	className?: string;
}

// Color + icon per status. Active = green, paused = amber, archived = muted.
const STATUS_STYLES: Record<
	AutomationStatus,
	{ label: string; icon: typeof CircleDot; classes: string }
> = {
	active: {
		label: "Active",
		icon: CircleDot,
		classes:
			"bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900/50",
	},
	paused: {
		label: "Paused",
		icon: Pause,
		classes:
			"bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900/50",
	},
	archived: {
		label: "Archived",
		icon: Archive,
		classes: "bg-muted text-muted-foreground border border-border/60",
	},
};

export function AutomationStatusBadge({ status, className }: AutomationStatusBadgeProps) {
	const { label, icon: Icon, classes } = STATUS_STYLES[status];
	return (
		<span
			className={cn(
				"inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium",
				classes,
				className
			)}
		>
			<Icon className="h-3 w-3" aria-hidden />
			{label}
		</span>
	);
}
