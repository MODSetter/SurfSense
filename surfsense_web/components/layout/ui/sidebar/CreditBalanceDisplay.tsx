"use client";

import { useQuery } from "@rocicorp/zero/react";
import { useIsAnonymous } from "@/contexts/anonymous-mode";
import { cn } from "@/lib/utils";
import { queries } from "@/zero/queries";

// Show the low-balance warning state once the wallet drops below $0.50.
const LOW_BALANCE_WARNING_MICROS = 500_000;

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
 * Unified credit-wallet balance shown in the sidebar.
 *
 * The single ``creditMicrosBalance`` replaces the former page-limit and
 * premium-credit meters. Values come from Zero (live-replicated from Postgres)
 * as integer micro-USD (1_000_000 == $1.00). A low-balance warning highlights
 * the amount when it falls below $0.50 so the user knows to top up or enable
 * auto-reload.
 */
export function CreditBalanceDisplay() {
	const isAnonymous = useIsAnonymous();
	const [me] = useQuery(queries.user.me({}));

	if (isAnonymous || !me) return null;

	const balanceMicros = me.creditMicrosBalance ?? 0;
	const isLow = balanceMicros < LOW_BALANCE_WARNING_MICROS;

	return (
		<div className="flex items-center justify-between text-xs">
			<span className="text-muted-foreground">Credits</span>
			<span
				className={cn(
					"font-medium tabular-nums",
					isLow ? "text-amber-600 dark:text-amber-500" : "text-foreground"
				)}
				title={isLow ? "Low balance — buy credits or enable auto-reload" : undefined}
			>
				{formatUsd(balanceMicros)}
			</span>
		</div>
	);
}
