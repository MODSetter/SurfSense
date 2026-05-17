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
					<Button
						type="button"
						variant="ghost"
						size="icon"
						onClick={() => setQuantity((q) => Math.max(1, q - 1))}
						disabled={quantity <= 1 || purchaseMutation.isPending}
						className="size-8 text-muted-foreground shadow-none transition-colors hover:bg-muted hover:text-white disabled:opacity-40"
					>
						<Minus className="h-3.5 w-3.5" />
					</Button>
					<span className="min-w-28 text-center text-lg font-semibold tabular-nums">
						{totalPages.toLocaleString()}
					</span>
					<Button
						type="button"
						variant="ghost"
						size="icon"
						onClick={() => setQuantity((q) => Math.min(100, q + 1))}
						disabled={quantity >= 100 || purchaseMutation.isPending}
						className="size-8 text-muted-foreground shadow-none transition-colors hover:bg-muted hover:text-white disabled:opacity-40"
					>
						<Plus className="h-3.5 w-3.5" />
					</Button>
				</div>

				{/* Quick-pick presets */}
				<div className="flex flex-wrap justify-center gap-1.5">
					{PRESET_MULTIPLIERS.map((m) => (
						<Button
							key={m}
							type="button"
							variant="ghost"
							onClick={() => setQuantity(m)}
							disabled={purchaseMutation.isPending}
							className={cn(
								"h-auto rounded-md px-2.5 py-1 text-xs font-medium tabular-nums transition-colors disabled:opacity-60",
								quantity === m
									? "bg-accent text-accent-foreground"
									: "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
							)}
						>
							{(m * PAGE_PACK_SIZE).toLocaleString()}
						</Button>
					))}
				</div>

				<div className="flex items-center justify-between rounded-lg border bg-muted/30 px-3 py-2">
					<span className="text-sm font-medium tabular-nums">
						{totalPages.toLocaleString()} pages
					</span>
					<span className="text-sm font-semibold tabular-nums">${totalPrice}</span>
				</div>

				<Button
					className="w-full"
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
