"use client";

import { useQuery } from "@rocicorp/zero/react";
import { Progress } from "@/components/ui/progress";
import { useIsAnonymous } from "@/contexts/anonymous-mode";
import { queries } from "@/zero/queries";

export function PremiumTokenUsageDisplay() {
	const isAnonymous = useIsAnonymous();
	const [me] = useQuery(queries.user.me({}));

	if (isAnonymous || !me) return null;

	const usagePercentage = Math.min(
		(me.premiumTokensUsed / Math.max(me.premiumTokensLimit, 1)) * 100,
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
					{formatTokens(me.premiumTokensUsed)} / {formatTokens(me.premiumTokensLimit)} tokens
				</span>
				<span className="font-medium">{usagePercentage.toFixed(0)}%</span>
			</div>
			<Progress value={usagePercentage} className="h-1.5 [&>div]:bg-purple-500" />
		</div>
	);
}
