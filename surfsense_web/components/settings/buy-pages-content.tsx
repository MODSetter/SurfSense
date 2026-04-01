"use client";

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

const PAGE_PACK_SIZE = 1000;
const PRICE_PER_PACK_USD = 1;
const PRESET_MULTIPLIERS = [1, 2, 5, 10, 25, 50] as const;

export function BuyPagesContent() {
	const params = useParams();
	const [quantity, setQuantity] = useState(1);
	const { data: stripeStatus } = useQuery({
		queryKey: ["stripe-status"],
		queryFn: () => stripeApiService.getStatus(),
	});

	const purchaseMutation = useMutation({
		mutationFn: stripeApiService.createCheckoutSession,
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

	const searchSpaceId = Number(params.search_space_id);
	const hasValidSearchSpace = Number.isFinite(searchSpaceId) && searchSpaceId > 0;
	const totalPages = quantity * PAGE_PACK_SIZE;
	const totalPrice = quantity * PRICE_PER_PACK_USD;

	if (stripeStatus && !stripeStatus.page_buying_enabled) {
		return (
			<div className="w-full space-y-3 text-center">
				<h2 className="text-xl font-bold tracking-tight">Buy Pages</h2>
				<p className="text-sm text-muted-foreground">Page purchases are temporarily unavailable.</p>
			</div>
		);
	}

	const handleBuyNow = () => {
		if (!hasValidSearchSpace) {
			toast.error("Unable to determine the current workspace for checkout.");
			return;
		}
		purchaseMutation.mutate({
			quantity,
			search_space_id: searchSpaceId,
		});
	};

	return (
		<div className="w-full space-y-5">
			<div className="text-center">
				<h2 className="text-xl font-bold tracking-tight">Buy Pages</h2>
				<p className="mt-1 text-sm text-muted-foreground">$1 per 1,000 pages, pay as you go</p>
			</div>

			<div className="space-y-3">
				{/* Stepper */}
				<div className="flex items-center justify-center gap-3">
					<button
						type="button"
						onClick={() => setQuantity((q) => Math.max(1, q - 1))}
						disabled={quantity <= 1 || purchaseMutation.isPending}
						className="flex h-8 w-8 items-center justify-center rounded-md border transition-colors hover:bg-muted disabled:opacity-40"
					>
						<Minus className="h-3.5 w-3.5" />
					</button>
					<span className="min-w-28 text-center text-lg font-semibold tabular-nums">
						{totalPages.toLocaleString()}
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

				{/* Quick-pick presets */}
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
									? "border-emerald-500 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
									: "border-border hover:border-emerald-500/40 hover:bg-muted/40"
							)}
						>
							{(m * PAGE_PACK_SIZE).toLocaleString()}
						</button>
					))}
				</div>

				<div className="flex items-center justify-between rounded-lg border bg-muted/30 px-3 py-2">
					<span className="text-sm font-medium tabular-nums">
						{totalPages.toLocaleString()} pages
					</span>
					<span className="text-sm font-semibold tabular-nums">${totalPrice}</span>
				</div>

				<Button
					className="w-full bg-emerald-600 text-white hover:bg-emerald-700"
					disabled={purchaseMutation.isPending || !hasValidSearchSpace}
					onClick={handleBuyNow}
				>
					{purchaseMutation.isPending ? (
						<>
							<Spinner size="xs" />
							Redirecting
						</>
					) : (
						<>
							Buy {totalPages.toLocaleString()} Pages for ${totalPrice}
						</>
					)}
				</Button>
				<p className="text-center text-[11px] text-muted-foreground">Secure checkout via Stripe</p>
			</div>
		</div>
	);
}
