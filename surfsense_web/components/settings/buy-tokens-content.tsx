"use client";

import { useQuery as useZeroQuery } from "@rocicorp/zero/react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Minus, Plus } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { stripeApiService } from "@/lib/apis/stripe-api.service";
import { AppError } from "@/lib/error";
import { cn } from "@/lib/utils";
import { queries } from "@/zero/queries";

const TOKEN_PACK_SIZE = 1_000_000;
const PRICE_PER_PACK_USD = 1;
const PRESET_MULTIPLIERS = [1, 2, 5, 10, 25, 50] as const;

export function BuyTokensContent() {
	const params = useParams();
	const searchSpaceId = Number(params?.search_space_id);
	const [quantity, setQuantity] = useState(1);

	// Server config flag: stays on REST, not per-user.
	const { data: tokenStatus } = useQuery({
		queryKey: ["token-status"],
		queryFn: () => stripeApiService.getTokenStatus(),
	});

	// Live per-user usage via Zero.
	const [me] = useZeroQuery(queries.user.me({}));

	const purchaseMutation = useMutation({
		mutationFn: stripeApiService.createTokenCheckoutSession,
		onSuccess: (response) => {
			window.location.assign(response.checkout_url);
		},
		onError: (error) => {
			if (error instanceof AppError && error.message) {
				toast.error(error.message);
				return;
			}
			toast.error("Failed to start checkout. Please try again.");
		},
	});

	const totalTokens = quantity * TOKEN_PACK_SIZE;
	const totalPrice = quantity * PRICE_PER_PACK_USD;

	if (tokenStatus && !tokenStatus.token_buying_enabled) {
		return (
			<div className="w-full space-y-3 text-center">
				<h2 className="text-xl font-bold tracking-tight">Buy Premium Tokens</h2>
				<p className="text-sm text-muted-foreground">
					Token purchases are temporarily unavailable.
				</p>
			</div>
		);
	}

	const used = me?.premiumTokensUsed ?? 0;
	const limit = me?.premiumTokensLimit ?? 0;
	// Mirrors the backend formula in stripe_routes.py:608 (max(0, limit - used)).
	const remaining = Math.max(0, limit - used);
	const usagePercentage = me ? Math.min((used / Math.max(limit, 1)) * 100, 100) : 0;

	return (
		<div className="w-full space-y-5">
			<div className="text-center">
				<h2 className="text-xl font-bold tracking-tight">Buy Premium Tokens</h2>
				<p className="mt-1 text-sm text-muted-foreground">$1 per 1M tokens, pay as you go</p>
			</div>

			{me && (
				<div className="rounded-lg border bg-muted/20 p-3 space-y-1.5">
					<div className="flex justify-between items-center text-xs">
						<span className="text-muted-foreground">
							{used.toLocaleString()} / {limit.toLocaleString()} premium tokens
						</span>
						<span className="font-medium">{usagePercentage.toFixed(0)}%</span>
					</div>
					<Progress value={usagePercentage} className="h-1.5" />
					<p className="text-[11px] text-muted-foreground">
						{remaining.toLocaleString()} tokens remaining
					</p>
				</div>
			)}

			<div className="space-y-3">
				<div className="flex items-center justify-center gap-3">
					<button
						type="button"
						onClick={() => setQuantity((q) => Math.max(1, q - 1))}
						disabled={quantity <= 1 || purchaseMutation.isPending}
						className="flex h-8 w-8 items-center justify-center rounded-md border transition-colors hover:bg-muted disabled:opacity-40"
					>
						<Minus className="h-3.5 w-3.5" />
					</button>
					<span className="min-w-32 text-center text-lg font-semibold tabular-nums">
						{(totalTokens / 1_000_000).toFixed(0)}M tokens
					</span>
					<button
						type="button"
						onClick={() => setQuantity((q) => Math.min(100, q + 1))}
						disabled={quantity >= 100 || purchaseMutation.isPending}
						className="flex h-8 w-8 items-center justify-center rounded-md border transition-colors hover:bg-muted disabled:opacity-40"
					>
						<Plus className="h-3.5 w-3.5" />
					</button>
				</div>

				<div className="flex flex-wrap justify-center gap-1.5">
					{PRESET_MULTIPLIERS.map((m) => (
						<button
							key={m}
							type="button"
							onClick={() => setQuantity(m)}
							disabled={purchaseMutation.isPending}
							className={cn(
								"rounded-md border px-2.5 py-1 text-xs font-medium tabular-nums transition-colors disabled:opacity-60",
								quantity === m
									? "border-purple-500 bg-purple-500/10 text-purple-600 dark:text-purple-400"
									: "border-border hover:border-purple-500/40 hover:bg-muted/40"
							)}
						>
							{m}M
						</button>
					))}
				</div>

				<div className="flex items-center justify-between rounded-lg border bg-muted/30 px-3 py-2">
					<span className="text-sm font-medium tabular-nums">
						{(totalTokens / 1_000_000).toFixed(0)}M premium tokens
					</span>
					<span className="text-sm font-semibold tabular-nums">${totalPrice}</span>
				</div>

				<Button
					className="w-full bg-purple-600 text-white hover:bg-purple-700"
					disabled={purchaseMutation.isPending}
					onClick={() => purchaseMutation.mutate({ quantity, search_space_id: searchSpaceId })}
				>
					{purchaseMutation.isPending ? (
						<>
							<Spinner size="xs" />
							Redirecting
						</>
					) : (
						<>
							Buy {(totalTokens / 1_000_000).toFixed(0)}M Tokens for ${totalPrice}
						</>
					)}
				</Button>
				<p className="text-center text-[11px] text-muted-foreground">Secure checkout via Stripe</p>
			</div>
		</div>
	);
}
