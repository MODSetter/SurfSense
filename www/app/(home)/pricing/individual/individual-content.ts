import {
	FAQ_EXPIRY,
	FAQ_FEATURE_REQUEST,
	FAQ_FREE_TRIAL,
	FAQ_NO_ACCOUNT,
	FAQ_RENEWAL,
	FAQ_WHAT_A_LICENCE_ADDS,
	INDIVIDUAL_LIST_PRICE,
	PLUGIN_PLATFORMS,
	type PricingQuestion,
} from "@/app/(home)/pricing/pricing-content";
import { EMAIL } from "@/components/site/site-content";
import {
	CheckmarkBadgeIcon,
	type Icon,
	LaptopIcon,
	Mail01Icon,
	Plug01Icon,
	SecurityCheckIcon,
	SourceCodeIcon,
	WifiOffIcon,
	Wrench01Icon,
} from "@/components/ui/icons";

/**
 * Copy for `/pricing/individual`, the page between the pricing card and Stripe.
 *
 * Every claim is sourced, and nothing here is new policy:
 *   - price and renewal: `pricing-content.ts` (the Payment Link is one-off, so
 *     renewal is a new file at the list price);
 *   - what the licence unlocks: `PLUGIN_PLATFORMS`, the Individual plan and the
 *     plugins page ("Ours read public pages without your own accounts");
 *   - after paying: `docs/architecture/license/portal.md` (success page
 *     download, emailed copy, no account) and `license/app.md` (Settings ›
 *     License, verified offline);
 *   - refund and expiry: terms section 5, quoted closely;
 *   - the feature build request: the maintainer's rules of 21 Oct 2026, also
 *     in terms section 5 and `FAQ_FEATURE_REQUEST`.
 */

export type Benefit = { title: string; body: string; icon: Icon };

const PLATFORM_LIST = `${PLUGIN_PLATFORMS.slice(0, -1).join(", ")} and ${PLUGIN_PLATFORMS.at(-1)}`;

export const BENEFITS: Benefit[] = [
	{
		title: "Every SurfSense plugin",
		body: `${PLATFORM_LIST}, plus the web crawler. They read public pages without your own accounts, from inside the app's agent.`,
		icon: Plug01Icon,
	},
	{
		title: "Unlimited, at a flat price",
		body: "No per-item metering and no credits to buy or top up.",
		icon: CheckmarkBadgeIcon,
	},
	{
		title: "Priority support",
		body: "Questions from licence holders are answered first.",
		icon: Mail01Icon,
	},
	{
		title: "1 feature build request a year",
		body: "Ask for something you need in SurfSense. If it fits, it goes to the top of the queue and ships in the open-source app.",
		icon: Wrench01Icon,
	},
];

export const FREE_STILL_APPLIES =
	"Everything in Free still applies: the full app on Windows, macOS and Linux and every update stay free forever, with or without a licence.";

export const RENEWAL_NOTE = `Then ${INDIVIDUAL_LIST_PRICE} a year, the list price. One payment, not a subscription: nothing charges again on its own, and renewing is a new licence file.`;

export const CHECKOUT_NOTE =
	"Checkout is on Stripe, which asks for your name, email and payment details. There is no account to create, and the licence is registered to that email.";

export const REFUND_NOTE =
	"Full refund within 30 days if the licence does not do what this page says.";

/** The feature build request, in the order someone uses it. */
export const FEATURE_REQUEST_STEPS: string[] = [
	`Email your request to ${EMAIL} from the address your licence is registered to. You have one per licence year.`,
	"Within 5 business days we reply with yes or no and, for a yes, the scope we would build.",
	"A request that fits about a week of engineering work and the direction of the product goes to the top of the queue, and ships in the open-source app for everyone.",
	"There is no fixed delivery date. If we decline a request, you can send another one instead.",
];

export type Reassurance = { title: string; body: string; icon: Icon };

export const REASSURANCES: Reassurance[] = [
	{
		title: "30-day refund",
		body: "If the licence does not do what this site says it does, email us within 30 days of buying it and we will refund it in full.",
		icon: SecurityCheckIcon,
	},
	{
		title: "The app never stops",
		body: "When a licence expires, the plugins and priority support stop. The app and every future version of it keep working, and nothing you made with it is locked or taken away.",
		icon: LaptopIcon,
	},
	{
		title: "Checked offline",
		body: "The app verifies the licence file's signature on your own machine and never contacts a licence server. Only SurfSense's plugins see your licence key, when you use them.",
		icon: WifiOffIcon,
	},
	{
		title: "Open source",
		body: "The app's code, the licence check included, is public on GitHub. You can read it, or build the app yourself.",
		icon: SourceCodeIcon,
	},
];

export const INDIVIDUAL_FAQ: PricingQuestion[] = [
	FAQ_WHAT_A_LICENCE_ADDS,
	FAQ_FEATURE_REQUEST,
	FAQ_RENEWAL,
	FAQ_EXPIRY,
	FAQ_NO_ACCOUNT,
	FAQ_FREE_TRIAL,
];
