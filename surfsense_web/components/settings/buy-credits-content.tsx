"use client";

import { useQuery as useZeroQuery } from "@rocicorp/zero/react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Minus, Plus } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { stripeApiService } from "@/lib/apis/stripe-api.service";
import { AppError } from "@/lib/error";
import { cn } from "@/lib/utils";
import { queries } from "@/zero/queries";

// One pack = $1.00 of credit, stored as 1_000_000 micro-USD on the backend.
// ETL page processing and premium turns are both debited from the same wallet
// at the actual cost, so $1 of credit always buys $1 of usage at cost.
const CREDIT_PER_PACK_MICROS = 1_000_000;
const PRICE_PER_PACK_USD = 1;
const PRESET_MULTIPLIERS = [1, 2, 5, 10, 25, 50, 100] as const;
const MIN_QUANTITY = 1;
const MAX_QUANTITY = 10_000;

const clampQuantity = (value: number) =>
	Math.min(MAX_QUANTITY, Math.max(MIN_QUANTITY, Math.floor(value)));

const formatUsd = (micros: number) => {
	// Clamp at $0.00 — the balance can dip slightly negative when actual cost
	// exceeds the pre-charge estimate.
	const dollars = Math.max(0, micros) / 1_000_000;
	if (dollars >= 100) return `$${dollars.toFixed(0)}`;
	if (dollars >= 1) return `$${dollars.toFixed(2)}`;
	if (dollars > 0) return `$${dollars.toFixed(3)}`;
	return "$0.00";
};

export function BuyCreditsContent() {
	const params = useParams();
	const searchSpaceId = Number(params?.search_space_id);
	const [quantity, setQuantity] = useState(1);
	// Raw text of the amount field so the user can clear it while typing;
	// committed back to a clamped integer on blur.
	const [amountInput, setAmountInput] = useState("1");

	const commitQuantity = (value: number) => {
		const clamped = clampQuantity(Number.isFinite(value) ? value : MIN_QUANTITY);
		setQuantity(clamped);
		setAmountInput(String(clamped));
	};

	// Server config flag: stays on REST, not per-user.
	const { data: creditStatus } = useQuery({
		queryKey: ["credit-status"],
		queryFn: () => stripeApiService.getCreditStatus(),
	});

	// Live per-user balance via Zero.
	const [me] = useZeroQuery(queries.user.me({}));

	const purchaseMutation = useMutation({
		mutationFn: stripeApiService.createCreditCheckoutSession,
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

	const totalCreditMicros = quantity * CREDIT_PER_PACK_MICROS;
	const totalPrice = quantity * PRICE_PER_PACK_USD;

	if (creditStatus && !creditStatus.credit_buying_enabled) {
		return (
			<div className="w-full space-y-3 text-center">
				<h2 className="text-xl font-bold tracking-tight">Buy Credits</h2>
				<p className="text-sm text-muted-foreground">
					Credit purchases are temporarily unavailable.
				</p>
			</div>
		);
	}

	const balanceMicros = me?.creditMicrosBalance ?? creditStatus?.credit_micros_balance ?? 0;

	return (
		<div className="w-full space-y-5">
			<div className="text-center">
				<h2 className="text-xl font-bold tracking-tight">Buy Credits</h2>
			</div>

			<div className="rounded-lg border bg-muted/20 p-3">
				<div className="flex items-center justify-between text-sm">
					<span className="text-muted-foreground">Current balance</span>
					<span className="font-semibold tabular-nums">{formatUsd(balanceMicros)}</span>
				</div>
			</div>

			<div className="space-y-3">
				<div className="flex items-center justify-center gap-3">
					<Button
						type="button"
						variant="ghost"
						size="icon"
						onClick={() => commitQuantity(quantity - 1)}
						disabled={quantity <= MIN_QUANTITY || purchaseMutation.isPending}
						className="size-8 text-muted-foreground shadow-none transition-colors hover:bg-muted hover:text-white disabled:opacity-40"
					>
						<Minus className="h-3.5 w-3.5" />
					</Button>
					<div className="flex items-baseline gap-1.5">
						<span className="text-lg font-semibold">$</span>
						<input
							type="text"
							inputMode="numeric"
							value={amountInput}
							onChange={(e) => {
								const raw = e.target.value.replace(/[^0-9]/g, "");
								setAmountInput(raw);
								const parsed = Number.parseInt(raw, 10);
								if (Number.isFinite(parsed)) {
									setQuantity(clampQuantity(parsed));
								}
							}}
							onBlur={() => commitQuantity(Number.parseInt(amountInput, 10))}
							disabled={purchaseMutation.isPending}
							aria-label="Credit amount in US dollars"
							className="w-20 rounded-md border bg-transparent px-2 py-1 text-center text-lg font-semibold tabular-nums outline-none focus:ring-2 focus:ring-ring disabled:opacity-60"
						/>
						<span className="text-sm text-muted-foreground">of credit</span>
					</div>
					<Button
						type="button"
						variant="ghost"
						size="icon"
						onClick={() => commitQuantity(quantity + 1)}
						disabled={quantity >= MAX_QUANTITY || purchaseMutation.isPending}
						className="size-8 text-muted-foreground shadow-none transition-colors hover:bg-muted hover:text-white disabled:opacity-40"
					>
						<Plus className="h-3.5 w-3.5" />
					</Button>
				</div>

				<div className="flex flex-wrap justify-center gap-1.5">
					{PRESET_MULTIPLIERS.map((m) => (
						<Button
							key={m}
							type="button"
							variant="ghost"
							onClick={() => commitQuantity(m)}
							disabled={purchaseMutation.isPending}
							className={cn(
								"h-auto rounded-md px-2.5 py-1 text-xs font-medium tabular-nums transition-colors disabled:opacity-60",
								quantity === m
									? "bg-accent text-accent-foreground"
									: "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
							)}
						>
							${m}
						</Button>
					))}
				</div>

				<div className="flex items-center justify-between rounded-lg border bg-muted/30 px-3 py-2">
					<span className="text-sm font-medium tabular-nums">
						${(totalCreditMicros / 1_000_000).toFixed(0)} of credit
					</span>
					<span className="text-sm font-semibold tabular-nums">${totalPrice}</span>
				</div>

				<Button
					className="w-full"
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
							Buy ${(totalCreditMicros / 1_000_000).toFixed(0)} of credit for ${totalPrice}
						</>
					)}
				</Button>
				<p className="text-center text-[11px] text-muted-foreground">Secure checkout via Stripe</p>
			</div>
		</div>
	);
}
