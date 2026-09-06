"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { stripeApiService } from "@/lib/apis/stripe-api.service";
import { AppError } from "@/lib/error";
import { getWorkspaceIdNumber } from "@/lib/route-params";

const PRO_PRICE_USD = 15;

const PRO_FEATURES = [
	"$6 of premium model usage every month",
	"Connector calls, web crawls, and document processing included",
	"Purchased credit kept as overage, spent only after the allowance",
	"Priority support on Discord",
];

/**
 * Renewal date for the "Active" panel, or null when there isn't a usable one.
 *
 * Returns null rather than a fallback string for both a missing and an
 * unparseable value, because the caller has a sentence that reads correctly
 * without a date — where `new Date(...)` on junk would render the words
 * "Invalid Date" to a paying customer.
 */
export const formatPeriodEnd = (iso: string | null): string | null => {
	if (!iso) return null;
	const date = new Date(iso);
	if (Number.isNaN(date.getTime())) return null;
	return date.toLocaleDateString(undefined, { month: "long", day: "numeric" });
};

/**
 * Upgrade-to-Pro card for the billing page.
 *
 * Renders nothing unless the backend reports a configured subscription price.
 * That is the normal case for self-hosted installs, where an upgrade button
 * would open a checkout the deployment cannot complete.
 */
export function PlanUpgradeCard() {
	const params = useParams();
	const workspaceId = getWorkspaceIdNumber(params) ?? 0;

	const { data: plan, isLoading } = useQuery({
		queryKey: ["plan-status"],
		queryFn: () => stripeApiService.getPlanStatus(),
	});

	const upgradeMutation = useMutation({
		mutationFn: stripeApiService.createSubscriptionCheckoutSession,
		onSuccess: (response) => {
			window.location.assign(response.checkout_url);
		},
		onError: (error) => {
			if (error instanceof AppError && error.message) {
				toast.error(error.message);
				return;
			}
			toast.error("Could not start checkout. Please try again.");
		},
	});

	if (isLoading || !plan?.subscription_available) return null;

	const renewsOn = formatPeriodEnd(plan.period_end);

	if (plan.plan === "pro") {
		return (
			<div className="w-full rounded-lg border bg-muted/20 p-4">
				<div className="flex items-center justify-between gap-3">
					<div className="min-w-0">
						<p className="text-sm font-semibold tracking-tight">SurfSense Pro</p>
						<p className="mt-0.5 text-xs text-muted-foreground">
							{renewsOn ? `Your allowance renews on ${renewsOn}.` : "Your subscription is active."}
						</p>
					</div>
					<span className="shrink-0 rounded-full bg-foreground/10 px-2.5 py-1 text-xs font-medium">
						Active
					</span>
				</div>
				{/* Cancellation lives in Stripe rather than here: the portal handles
				    proration and payment-method changes, which would otherwise all
				    need building and keeping correct. */}
				<p className="mt-3 text-xs text-muted-foreground">
					To change or cancel your plan, use the billing link in your Stripe receipt email.
				</p>
			</div>
		);
	}

	return (
		<div className="w-full space-y-4 rounded-lg border p-4">
			<div className="flex items-baseline justify-between gap-3">
				<div>
					<h2 className="text-base font-semibold tracking-tight">Upgrade to Pro</h2>
					<p className="mt-0.5 text-xs text-muted-foreground">Billed monthly. Cancel any time.</p>
				</div>
				<p className="shrink-0 text-lg font-semibold tabular-nums">
					${PRO_PRICE_USD}
					<span className="text-xs font-normal text-muted-foreground">/mo</span>
				</p>
			</div>

			<ul className="space-y-1.5">
				{PRO_FEATURES.map((feature) => (
					<li key={feature} className="flex items-start gap-2 text-xs text-muted-foreground">
						<Check className="mt-0.5 size-3.5 shrink-0 text-foreground" />
						<span>{feature}</span>
					</li>
				))}
			</ul>

			<Button
				className="w-full"
				onClick={() => upgradeMutation.mutate({ workspace_id: workspaceId })}
				disabled={upgradeMutation.isPending || workspaceId <= 0}
			>
				{upgradeMutation.isPending ? (
					<>
						<Spinner size="xs" />
						Redirecting
					</>
				) : (
					<>Upgrade to Pro</>
				)}
			</Button>
		</div>
	);
}
