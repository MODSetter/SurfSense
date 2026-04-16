"use client";

import { useQuery } from "@tanstack/react-query";
import { Progress } from "@/components/ui/progress";
import { useIsAnonymous } from "@/contexts/anonymous-mode";
import { stripeApiService } from "@/lib/apis/stripe-api.service";

export function PremiumTokenUsageDisplay() {
	const isAnonymous = useIsAnonymous();
	const { data: tokenStatus } = useQuery({
		queryKey: ["token-status"],
		queryFn: () => stripeApiService.getTokenStatus(),
		staleTime: 60_000,
		enabled: !isAnonymous,
	});

	if (!tokenStatus) return null;

	const usagePercentage = Math.min(
		(tokenStatus.premium_tokens_used / Math.max(tokenStatus.premium_tokens_limit, 1)) * 100,
		100
	);

	const formatTokens = (n: number) => {
		if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
		if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
		return n.toLocaleString();
	};

	return (
		<div className="space-y-1.5">
			<div className="flex justify-between items-center text-xs">
				<span className="text-muted-foreground">
					{formatTokens(tokenStatus.premium_tokens_used)} /{" "}
					{formatTokens(tokenStatus.premium_tokens_limit)} tokens
				</span>
				<span className="font-medium">{usagePercentage.toFixed(0)}%</span>
			</div>
			<Progress value={usagePercentage} className="h-1.5 [&>div]:bg-purple-500" />
		</div>
	);
}
