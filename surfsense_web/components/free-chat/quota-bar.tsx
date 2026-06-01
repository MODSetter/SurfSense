"use client";

import { OctagonAlert, Orbit } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
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
		<div className={cn("flex flex-col gap-1.5", className)}>
			<div className="flex items-center justify-between text-xs">
				<span className="text-muted-foreground">
					{used.toLocaleString()} / {limit.toLocaleString()} tokens
				</span>
				{isExceeded ? (
					<span className="font-medium text-destructive">Limit reached</span>
				) : isWarning ? (
					<span className="flex items-center gap-1 font-medium text-highlight">
						<OctagonAlert className="size-3" />
						{remaining.toLocaleString()} remaining
					</span>
				) : (
					<span className="font-medium">{percentage.toFixed(0)}%</span>
				)}
			</div>
			<Progress value={percentage} className="h-1.5" />
			{isExceeded && (
				<Button asChild size="sm" className="mt-0.5 w-full">
					<Link href="/register">
						<Orbit data-icon="inline-start" />
						Create free account for 5M more tokens
					</Link>
				</Button>
			)}
		</div>
	);
}
