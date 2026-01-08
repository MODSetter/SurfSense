"use client";

import { Mail } from "lucide-react";
import { Progress } from "@/components/ui/progress";

interface PageUsageDisplayProps {
	pagesUsed: number;
	pagesLimit: number;
}

export function PageUsageDisplay({ pagesUsed, pagesLimit }: PageUsageDisplayProps) {
	const usagePercentage = (pagesUsed / pagesLimit) * 100;

	return (
		<div className="px-3 py-3 border-t">
			<div className="space-y-2">
				<div className="flex justify-between items-center text-xs">
					<span className="text-muted-foreground">
						{pagesUsed.toLocaleString()} / {pagesLimit.toLocaleString()} pages
					</span>
					<span className="font-medium">{usagePercentage.toFixed(0)}%</span>
				</div>
				<Progress value={usagePercentage} className="h-1.5" />
				<a
					href="mailto:rohan@surfsense.com?subject=Request%20to%20Increase%20Page%20Limits"
					className="flex items-center gap-1.5 text-[10px] text-muted-foreground hover:text-primary transition-colors"
				>
					<Mail className="h-3 w-3 shrink-0" />
					<span>Contact to increase limits</span>
				</a>
			</div>
		</div>
	);
}
