"use client";
import { AlertCircle, CheckCircle2, Clock, Loader2, TimerOff, XCircle } from "lucide-react";
import type { RunStatus } from "@/contracts/types/automation.types";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<
	RunStatus,
	{ label: string; icon: typeof CheckCircle2; classes: string; spin?: boolean }
> = {
	pending: {
		label: "Pending",
		icon: Clock,
		classes: "bg-muted text-muted-foreground border-border/60",
	},
	running: {
		label: "Running",
		icon: Loader2,
		classes: "bg-blue-500/10 text-blue-600 border-blue-500/20",
		spin: true,
	},
	succeeded: {
		label: "Succeeded",
		icon: CheckCircle2,
		classes: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20",
	},
	failed: {
		label: "Failed",
		icon: XCircle,
		classes: "bg-destructive/10 text-destructive border-destructive/20",
	},
	cancelled: {
		label: "Cancelled",
		icon: AlertCircle,
		classes: "bg-muted text-muted-foreground border-border/60",
	},
	timed_out: {
		label: "Timed out",
		icon: TimerOff,
		classes: "bg-amber-500/10 text-amber-600 border-amber-500/20",
	},
};

export function RunStatusBadge({ status, className }: { status: RunStatus; className?: string }) {
	const { label, icon: Icon, classes, spin } = STATUS_STYLES[status];
	return (
		<span
			className={cn(
				"inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium",
				classes,
				className
			)}
		>
			<Icon className={cn("h-3 w-3", spin && "animate-spin")} aria-hidden />
			{label}
		</span>
	);
}
