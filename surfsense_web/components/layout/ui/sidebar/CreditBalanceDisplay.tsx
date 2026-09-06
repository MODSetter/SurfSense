"use client";

import { useQuery } from "@rocicorp/zero/react";
import { useQuery as useRestQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useIsAnonymous } from "@/contexts/anonymous-mode";
import { spendableMicros } from "@/contracts/types/stripe.types";
import { stripeApiService } from "@/lib/apis/stripe-api.service";
import { formatRelativeFutureDate } from "@/lib/format-date";
import { cn } from "@/lib/utils";
import { queries } from "@/zero/queries";

// Warn once the wallet drops below $0.50 of spendable funds.
const LOW_BALANCE_WARNING_MICROS = 500_000;

const PLAN_LABELS: Record<string, string> = { free: "Free", pro: "Pro" };

function formatUsd(micros: number): string {
	// Clamp at $0.00 — the balance can dip slightly negative when the actual
	// cost of a job exceeds the pre-charge estimate.
	const dollars = Math.max(0, micros) / 1_000_000;
	if (dollars >= 100) return `$${dollars.toFixed(0)}`;
	if (dollars >= 1) return `$${dollars.toFixed(2)}`;
	// Sub-dollar balances need extra precision so the user can still tell what
	// is left ("$0.042 of credit") instead of rounding to "$0.00".
	if (dollars > 0) return `$${dollars.toFixed(3)}`;
	return "$0.00";
}

/**
 * Plan indicator for the sidebar, with the wallet detail on hover.
 *
 * Shows the plan name rather than a dollar total on purpose. A bare figure
 * invites the wrong comparison — a subscriber who pays $15 and reads "$6.00"
 * has no way to tell that it is a monthly allocation that refills, so it looks
 * like the difference went missing. The tooltip carries the exact numbers.
 *
 * The two wallet buckets are added because a debit spends the plan allowance
 * before the permanent balance, so the balance alone reads `$0.00` for anyone
 * living inside their monthly allowance, which is most users. They arrive by
 * different routes: the balance comes from Zero, live-replicated from Postgres,
 * so a purchase appears at once, while the allowance is not in the Zero
 * publication and comes over REST on the interval below. Both are integer
 * micro-USD (1_000_000 == $1.00).
 */
export function CreditBalanceDisplay() {
	const isAnonymous = useIsAnonymous();
	const [me] = useQuery(queries.user.me({}));
	const { data: creditStatus } = useRestQuery({
		queryKey: ["credit-status"],
		queryFn: () => stripeApiService.getCreditStatus(),
		// Nothing pushes a change when a turn spends the allowance, and for a
		// user whose balance is $0 the spend never touches the Zero-replicated
		// column either — so without a poll the number would sit still while
		// their month drains. TanStack pauses this while the tab is hidden.
		refetchInterval: 60_000,
		enabled: !isAnonymous,
	});

	if (isAnonymous || !me) return null;

	const plan = creditStatus?.plan ?? "free";
	const planLabel = PLAN_LABELS[plan] ?? plan;
	const allowanceLeft = creditStatus?.credit_micros_allowance ?? 0;
	const allowanceGranted = creditStatus?.allowance_granted_micros ?? 0;
	const purchased = me.creditMicrosBalance ?? 0;
	const totalMicros = spendableMicros(allowanceLeft, purchased);
	const isLow = totalMicros < LOW_BALANCE_WARNING_MICROS;
	const resetsIn = creditStatus?.allowance_period_end
		? formatRelativeFutureDate(creditStatus.allowance_period_end)
		: null;

	return (
		<div className="flex items-center justify-between text-xs">
			<span className="text-muted-foreground">Plan</span>
			<Tooltip>
				<TooltipTrigger asChild>
					<Badge
						variant="outline"
						className={cn(
							"cursor-default tabular-nums",
							isLow && "border-amber-500/40 text-amber-600 dark:text-amber-500"
						)}
					>
						{planLabel}
					</Badge>
				</TooltipTrigger>
				<TooltipContent side="right" className="max-w-60 space-y-1 px-3 py-2">
					<p className="font-semibold">{planLabel} plan</p>
					{allowanceGranted > 0 ? (
						<p>
							{formatUsd(allowanceLeft)} of {formatUsd(allowanceGranted)} monthly usage left
							{resetsIn ? `, resets ${resetsIn}` : ""}
						</p>
					) : null}
					{purchased > 0 ? (
						<p>{formatUsd(purchased)} purchased credit, which does not expire</p>
					) : null}
					{totalMicros <= 0 ? (
						<p className="text-amber-600 dark:text-amber-500">
							Premium models are paused until this refills or you add credit.
						</p>
					) : null}
				</TooltipContent>
			</Tooltip>
		</div>
	);
}
