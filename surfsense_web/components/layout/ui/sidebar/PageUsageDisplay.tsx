"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Progress } from "@/components/ui/progress";

interface PageUsageDisplayProps {
	pagesUsed: number;
	pagesLimit: number;
}

export function PageUsageDisplay({ pagesUsed, pagesLimit }: PageUsageDisplayProps) {
	const params = useParams();
	const searchSpaceId = params.search_space_id;
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
				<Link
					href={`/dashboard/${searchSpaceId}/more-pages`}
					className="flex items-center gap-1.5 text-[10px] text-muted-foreground hover:text-primary transition-colors"
				>
					<Plus className="h-3 w-3 shrink-0" />
					<span>Get More Pages</span>
				</Link>
			</div>
		</div>
	);
}
