"use client";

import { OctagonAlert, Orbit } from "lucide-react";
import Link from "next/link";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface QuotaBarProps {
	used: number;
	limit: number;
	warningThreshold: number;
	className?: string;
}

export function QuotaBar({ used, limit, warningThreshold, className }: QuotaBarProps) {
	const percentage = Math.min((used / limit) * 100, 100);
	const remaining = Math.max(limit - used, 0);
	const isWarning = used >= warningThreshold;
	const isExceeded = used >= limit;

	return (
		<div className={cn("space-y-1.5", className)}>
			<div className="flex justify-between items-center text-xs">
				<span className="text-muted-foreground">
					{used.toLocaleString()} / {limit.toLocaleString()} tokens
				</span>
				{isExceeded ? (
					<span className="font-medium text-red-500">Limit reached</span>
				) : isWarning ? (
					<span className="font-medium text-amber-500 flex items-center gap-1">
						<OctagonAlert className="h-3 w-3" />
						{remaining.toLocaleString()} remaining
					</span>
				) : (
					<span className="font-medium">{percentage.toFixed(0)}%</span>
				)}
			</div>
			<Progress
				value={percentage}
				className={cn(
					"h-1.5",
					isExceeded && "[&>div]:bg-red-500",
					isWarning && !isExceeded && "[&>div]:bg-amber-500"
				)}
			/>
			{isExceeded && (
				<Link
					href="/register"
					className="flex items-center justify-center gap-1.5 rounded-md bg-linear-to-r from-purple-600 to-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90"
				>
					<Orbit className="h-3 w-3" />
					Create free account for 5M more tokens
				</Link>
			)}
		</div>
	);
}
