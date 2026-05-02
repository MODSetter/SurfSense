"use client";

import { useQuery } from "@rocicorp/zero/react";
import { Progress } from "@/components/ui/progress";
import { useIsAnonymous } from "@/contexts/anonymous-mode";
import { queries } from "@/zero/queries";

/**
 * Premium credit balance shown in the sidebar.
 *
 * Values come from Zero (live-replicated from Postgres) and are stored as
 * integer micro-USD (1_000_000 == $1.00). We render in dollars because
 * users top up at $1/pack and the credit gets debited at actual provider
 * cost.
 */
export function PremiumTokenUsageDisplay() {
	const isAnonymous = useIsAnonymous();
	const [me] = useQuery(queries.user.me({}));

	if (isAnonymous || !me) return null;

	const usagePercentage = Math.min(
		(me.premiumCreditMicrosUsed / Math.max(me.premiumCreditMicrosLimit, 1)) * 100,
		100
	);

	const formatUsd = (micros: number) => {
		const dollars = micros / 1_000_000;
		if (dollars >= 100) return `$${dollars.toFixed(0)}`;
		if (dollars >= 1) return `$${dollars.toFixed(2)}`;
		// Sub-dollar balances need extra precision so the bar still tells the
		// user what's left ("$0.04 of credit") instead of rounding to "$0".
		if (dollars > 0) return `$${dollars.toFixed(3)}`;
		return "$0";
	};

	return (
		<div className="space-y-1.5">
			<div className="flex justify-between items-center text-xs">
				<span className="text-muted-foreground">
					{formatUsd(me.premiumCreditMicrosUsed)} / {formatUsd(me.premiumCreditMicrosLimit)} of
					credit
				</span>
				<span className="font-medium">{usagePercentage.toFixed(0)}%</span>
			</div>
			<Progress value={usagePercentage} className="h-1.5 [&>div]:bg-purple-500" />
		</div>
	);
}
