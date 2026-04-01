"use client";

import { useQuery } from "@tanstack/react-query";
import { CreditCard, Zap } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { stripeApiService } from "@/lib/apis/stripe-api.service";

interface PageUsageDisplayProps {
	pagesUsed: number;
	pagesLimit: number;
}

export function PageUsageDisplay({ pagesUsed, pagesLimit }: PageUsageDisplayProps) {
	const params = useParams();
	const searchSpaceId = params?.search_space_id ?? "";
	const usagePercentage = (pagesUsed / pagesLimit) * 100;
	const { data: stripeStatus } = useQuery({
		queryKey: ["stripe-status"],
		queryFn: () => stripeApiService.getStatus(),
	});
	const pageBuyingEnabled = stripeStatus?.page_buying_enabled ?? true;

	return (
		<div className="px-3 py-3 border-t">
			<div className="space-y-1.5">
				<div className="flex justify-between items-center text-xs">
					<span className="text-muted-foreground">
						{pagesUsed.toLocaleString()} / {pagesLimit.toLocaleString()} pages
					</span>
					<span className="font-medium">{usagePercentage.toFixed(0)}%</span>
				</div>
				<Progress value={usagePercentage} className="h-1.5" />
				<Link
					href={`/dashboard/${searchSpaceId}/more-pages`}
					className="group flex w-full items-center justify-between rounded-md px-1.5 py-1 -mx-1.5 transition-colors hover:bg-accent"
				>
					<span className="flex items-center gap-1.5 text-xs text-muted-foreground group-hover:text-accent-foreground">
						<Zap className="h-3 w-3 shrink-0" />
						Get Free Pages
					</span>
					<Badge className="h-4 rounded px-1 text-[10px] font-semibold leading-none bg-emerald-600 text-white border-transparent hover:bg-emerald-600">
						FREE
					</Badge>
				</Link>
				{pageBuyingEnabled && (
					<Link
						href={`/dashboard/${searchSpaceId}/buy-pages`}
						className="group flex w-full items-center justify-between rounded-md px-1.5 py-1 -mx-1.5 transition-colors hover:bg-accent"
					>
						<span className="flex items-center gap-1.5 text-xs text-muted-foreground group-hover:text-accent-foreground">
							<CreditCard className="h-3 w-3 shrink-0" />
							Buy Pages
						</span>
						<span className="text-[10px] font-medium text-muted-foreground">
							$1/1k
						</span>
					</Link>
				)}
			</div>
		</div>
	);
}
