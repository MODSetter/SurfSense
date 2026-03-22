"use client";

import { useSetAtom } from "jotai";
import { Zap } from "lucide-react";
import { morePagesDialogAtom } from "@/atoms/settings/settings-dialog.atoms";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

interface PageUsageDisplayProps {
	pagesUsed: number;
	pagesLimit: number;
}

export function PageUsageDisplay({ pagesUsed, pagesLimit }: PageUsageDisplayProps) {
	const setMorePagesOpen = useSetAtom(morePagesDialogAtom);
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
				<button
					type="button"
					onClick={() => setMorePagesOpen(true)}
					className="group flex w-full items-center justify-between rounded-md px-1.5 py-1 -mx-1.5 transition-colors hover:bg-accent"
				>
					<span className="flex items-center gap-1.5 text-xs text-muted-foreground group-hover:text-accent-foreground">
						<Zap className="h-3 w-3 shrink-0" />
						Upgrade to PRO
					</span>
					<Badge className="h-4 rounded px-1 text-[10px] font-semibold leading-none bg-emerald-600 text-white border-transparent hover:bg-emerald-600">
						FREE
					</Badge>
				</button>
			</div>
		</div>
	);
}
