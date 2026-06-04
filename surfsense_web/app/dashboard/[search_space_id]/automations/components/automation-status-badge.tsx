"use client";
import type { AutomationStatus } from "@/contracts/types/automation.types";
import { cn } from "@/lib/utils";

interface AutomationStatusBadgeProps {
	status: AutomationStatus;
	className?: string;
}

// Small borderless status pills, matching model-selector badges.
const STATUS_STYLES: Record<
	AutomationStatus,
	{ label: string; classes: string }
> = {
	active: {
		label: "Active",
		classes:
			"bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300",
	},
	paused: {
		label: "Paused",
		classes:
			"bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300",
	},
	archived: {
		label: "Archived",
		classes: "bg-muted text-muted-foreground",
	},
};

export function AutomationStatusBadge({ status, className }: AutomationStatusBadgeProps) {
	const { label, classes } = STATUS_STYLES[status];
	return (
		<span
			className={cn(
				"inline-flex items-center rounded-md border-0 px-1.5 py-0 text-sm font-medium leading-5",
				classes,
				className
			)}
		>
			{label}
		</span>
	);
}
