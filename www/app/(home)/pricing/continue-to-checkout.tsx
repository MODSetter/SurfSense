"use client";

import { useEffect, useState } from "react";
import { HomeButton } from "@/components/site/home-button";
import { cn } from "@/components/ui/cn";
import { ArrowRightIcon } from "@/components/ui/icons";
import { currentChannel } from "@/features/funnel-attribution/current-channel";
import {
	type CheckoutPlan,
	trackCheckoutStarted,
} from "@/features/funnel-attribution/funnel-events";
import { checkoutHref, isPaymentLink } from "./checkout-link";

function isPlainClick(event: React.MouseEvent<HTMLAnchorElement>): boolean {
	return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
}

/**
 * A checkout page's one primary action, shared by `/pricing/individual` and
 * `/pricing/business`. A plain anchor, so it still reaches checkout with scripts
 * off or opened in a new tab; the channel tag is added once the page is
 * interactive and recomputed at click time, when PostHog has loaded.
 */
export function ContinueToCheckout({
	buyUrl,
	plan,
	className,
}: {
	/** The plan's Stripe Payment Link, or `/contact` when none is configured. */
	buyUrl: string;
	plan: CheckoutPlan;
	className?: string;
}) {
	const paymentLink = isPaymentLink(buyUrl);
	const [href, setHref] = useState(buyUrl);

	useEffect(() => {
		if (paymentLink) setHref(checkoutHref(buyUrl, currentChannel()));
	}, [buyUrl, paymentLink]);

	function handleClick(event: React.MouseEvent<HTMLAnchorElement>) {
		if (!paymentLink) return;
		const channel = currentChannel();
		trackCheckoutStarted(plan, channel);
		const checkout = checkoutHref(buyUrl, channel);
		if (!isPlainClick(event)) {
			// A new tab follows the anchor, so it must carry the channel just counted.
			event.currentTarget.href = checkout;
			setHref(checkout);
			return;
		}
		event.preventDefault();
		window.location.assign(checkout);
	}

	return (
		<HomeButton asChild size="2xl" static className={cn("w-full rounded-full", className)}>
			<a href={href} onClick={handleClick}>
				{paymentLink ? "Continue to checkout" : "Contact us to buy"}
				<ArrowRightIcon aria-hidden="true" className="size-5" />
			</a>
		</HomeButton>
	);
}
