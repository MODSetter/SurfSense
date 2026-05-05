"use client";

import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import type { FinalizeCheckoutResponse } from "@/contracts/types/stripe.types";
import { stripeApiService } from "@/lib/apis/stripe-api.service";

type FinalizeState =
	| { kind: "loading" }
	| { kind: "completed"; data: FinalizeCheckoutResponse }
	| { kind: "pending"; data: FinalizeCheckoutResponse }
	| { kind: "still_pending"; data: FinalizeCheckoutResponse }
	| { kind: "failed"; data: FinalizeCheckoutResponse }
	| { kind: "error"; message: string }
	| { kind: "no_session" };

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_ATTEMPTS = 15; // ~30s total before falling back to the still_pending state

export default function PurchaseSuccessPage() {
	const params = useParams();
	const searchParams = useSearchParams();
	const searchSpaceId = String(params.search_space_id ?? "");
	const sessionId = searchParams.get("session_id");

	const [state, setState] = useState<FinalizeState>(
		sessionId ? { kind: "loading" } : { kind: "no_session" }
	);
	// Tracks active polling so component unmount cancels it
	const cancelledRef = useRef(false);

	useEffect(() => {
		if (!sessionId) return;

		cancelledRef.current = false;

		const poll = async (attempt: number): Promise<void> => {
			if (cancelledRef.current) return;
			try {
				const data = await stripeApiService.finalizeCheckout(sessionId);
				if (cancelledRef.current) return;

				if (data.status === "completed") {
					setState({ kind: "completed", data });
					return;
				}
				if (data.status === "failed") {
					setState({ kind: "failed", data });
					return;
				}

				// Status is "pending" - either the user paid via async
				// payment method (Klarna, ACH) or webhook + finalize both
				// raced and lost. Keep polling up to MAX_POLL_ATTEMPTS,
				// then fall back to a friendlier message that explains
				// fulfilment may complete asynchronously.
				if (attempt < MAX_POLL_ATTEMPTS) {
					setState({ kind: "pending", data });
					setTimeout(() => poll(attempt + 1), POLL_INTERVAL_MS);
				} else {
					setState({ kind: "still_pending", data });
				}
			} catch (err) {
				if (cancelledRef.current) return;
				const message = err instanceof Error ? err.message : "Unable to finalize checkout.";
				setState({ kind: "error", message });
			}
		};

		void poll(1);

		return () => {
			cancelledRef.current = true;
		};
	}, [sessionId]);

	return (
		<div className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4 py-8">
			<Card className="w-full max-w-lg">
				<CardHeader className="text-center">
					{state.kind === "loading" || state.kind === "pending" ? (
						<Loader2 className="mx-auto h-10 w-10 animate-spin text-primary" />
					) : state.kind === "completed" ? (
						<CheckCircle2 className="mx-auto h-10 w-10 text-emerald-500" />
					) : (
						<AlertCircle className="mx-auto h-10 w-10 text-amber-500" />
					)}
					<CardTitle className="text-2xl">
						{state.kind === "loading" && "Confirming payment…"}
						{state.kind === "pending" && "Processing your payment…"}
						{state.kind === "still_pending" && "Payment still processing"}
						{state.kind === "completed" && "Purchase complete"}
						{state.kind === "failed" && "Purchase failed"}
						{state.kind === "error" && "Couldn't confirm payment"}
						{state.kind === "no_session" && "Purchase complete"}
					</CardTitle>
					<CardDescription>
						{state.kind === "loading" && "We're verifying your payment with Stripe."}
						{state.kind === "pending" &&
							"Your bank is taking a moment to confirm. This usually takes 5–30 seconds."}
						{state.kind === "still_pending" &&
							"Your payment is still being processed by your bank. We'll apply your purchase as soon as it clears — usually within a few minutes. You can safely close this page."}
						{state.kind === "completed" &&
							(state.data.purchase_type === "page_packs"
								? `Added ${formatNumber(state.data.pages_granted ?? 0)} pages to your account.`
								: `Added ${formatCredit(state.data.premium_credit_micros_granted ?? 0)} of premium credit to your account.`)}
						{state.kind === "failed" &&
							"Stripe reported the checkout as failed or expired. Your card was not charged."}
						{state.kind === "error" &&
							"Don't worry — if your card was charged, your purchase will still apply within a minute or two."}
						{state.kind === "no_session" &&
							"Your purchase is being applied to your account."}
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-3 text-center">
					{state.kind === "completed" && state.data.purchase_type === "page_packs" && (
						<p className="text-sm text-muted-foreground">
							New balance: {formatNumber(state.data.pages_limit ?? 0)} total pages
							{typeof state.data.pages_used === "number"
								? ` (${formatNumber((state.data.pages_limit ?? 0) - state.data.pages_used)} remaining)`
								: ""}
						</p>
					)}
					{state.kind === "completed" && state.data.purchase_type === "premium_tokens" && (
						<p className="text-sm text-muted-foreground">
							New premium credit balance: {formatCredit(state.data.premium_credit_micros_limit ?? 0)}
						</p>
					)}
					{state.kind === "error" && (
						<p className="text-sm text-muted-foreground">{state.message}</p>
					)}
				</CardContent>
				<CardFooter className="flex flex-col gap-2">
					<Button asChild className="w-full">
						<Link href={`/dashboard/${searchSpaceId}/new-chat`}>Back to Dashboard</Link>
					</Button>
					<Button asChild variant="outline" className="w-full">
						<Link href={`/dashboard/${searchSpaceId}/buy-more`}>Buy More</Link>
					</Button>
				</CardFooter>
			</Card>
		</div>
	);
}

function formatNumber(n: number): string {
	return new Intl.NumberFormat("en-US").format(n);
}

function formatCredit(micros: number): string {
	const dollars = micros / 1_000_000;
	return new Intl.NumberFormat("en-US", {
		style: "currency",
		currency: "USD",
		maximumFractionDigits: 2,
	}).format(dollars);
}
