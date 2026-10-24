"use client";

import { useEffect, useState } from "react";
import { BUY_INDIVIDUAL_URL } from "@/app/(home)/pricing/pricing-content";
import { HomeButton } from "@/components/site/home-button";
import { cn } from "@/components/ui/cn";
import { ArrowRightIcon } from "@/components/ui/icons";
import { currentChannel } from "@/features/funnel-attribution/current-channel";
import { trackCheckoutStarted } from "@/features/funnel-attribution/funnel-events";
import { checkoutHref, isPaymentLink } from "./checkout-link";

const PAYMENT_LINK = isPaymentLink(BUY_INDIVIDUAL_URL);

function isPlainClick(event: React.MouseEvent<HTMLAnchorElement>): boolean {
	return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
}

/**
 * The page's one primary action. A plain anchor, so it still reaches checkout
 * with scripts off or opened in a new tab; the channel tag is added once the
 * page is interactive and recomputed at click time, when PostHog has loaded.
 */
export function ContinueToCheckout({ className }: { className?: string }) {
	const [href, setHref] = useState(BUY_INDIVIDUAL_URL);

	useEffect(() => {
		if (PAYMENT_LINK) setHref(checkoutHref(BUY_INDIVIDUAL_URL, currentChannel()));
	}, []);

	function handleClick(event: React.MouseEvent<HTMLAnchorElement>) {
		if (!PAYMENT_LINK) return;
		const channel = currentChannel();
		trackCheckoutStarted(channel);
		const checkout = checkoutHref(BUY_INDIVIDUAL_URL, channel);
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
				{PAYMENT_LINK ? "Continue to checkout" : "Contact us to buy"}
				<ArrowRightIcon aria-hidden="true" className="size-5" />
			</a>
		</HomeButton>
	);
}
