import {
	FAQ_BUSINESS_LAPSE,
	FAQ_BUSINESS_NO_ACCOUNT,
	FAQ_BUSINESS_RENEWAL,
	FAQ_BUSINESS_TRIAL,
	FAQ_CANCEL_OR_CHANGE,
	FAQ_WHAT_BUSINESS_ADDS,
	FAQ_WHO_NEEDS_BUSINESS,
	WHAT_EACH_JOB_DOES,
} from "@/app/(home)/pricing/business-pricing-content";
import type { PricingQuestion } from "@/app/(home)/pricing/pricing-content";
import { EMAIL } from "@/components/site/site-content";
import {
	ClipboardCheckIcon,
	type Icon,
	LaptopIcon,
	Mail01Icon,
	SecurityCheckIcon,
	SourceCodeIcon,
	UserCircleIcon,
	WifiOffIcon,
	Wrench01Icon,
} from "@/components/ui/icons";
import { FURTHER_PERSON_PRICE, yearlyPriceLabel } from "../business-price";

/**
 * Copy for `/pricing/business`, the page between the Business card and Stripe.
 *
 * Every claim is ADR 0080's or ADR 0083's, or carried over from the retired `/pricing/individual`,
 * whose page this replaced: the yearly renewal stated before payment, cancellation and seat changes through
 * Stripe's emailed customer portal, people counted rather than devices, the 30 days before
 * a lapse stops new job runs, and terms section 5's refund.
 */

/** The Business Payment Link. Empty falls back to `/contact`, as Individual's does. */
export const BUY_BUSINESS_URL = process.env.NEXT_PUBLIC_STRIPE_LICENSE_BUSINESS_URL || "/contact";

const FURTHER = yearlyPriceLabel(FURTHER_PERSON_PRICE);

export type Benefit = { title: string; body: string; icon: Icon };

export const BENEFITS: Benefit[] = [
	{
		title: "The job plugins",
		body: `${WHAT_EACH_JOB_DOES} Further jobs join Business as they ship.`,
		icon: ClipboardCheckIcon,
	},
	{
		title: "Priced per person",
		body: "Business counts the people at your firm who use job plugins, not their computers. You say how many at checkout and confirm the number at each renewal.",
		icon: UserCircleIcon,
	},
	{
		title: "Priority support",
		body: "Questions from licence holders are answered first.",
		icon: Mail01Icon,
	},
	{
		title: "1 feature build request a year",
		body: "Ask for something your firm needs in SurfSense. If it fits, it goes to the top of the queue and ships in the open-source app.",
		icon: Wrench01Icon,
	},
];

export const FREE_STILL_APPLIES =
	"Everything in Free still applies: the full app on Windows, macOS and Linux, reading web pages, YouTube and web search, and every update stay free forever, with or without a licence.";

export const FURTHER_PEOPLE_NOTE = `Each further person adds ${FURTHER} a year. A founding price: a price change applies only at renewal, after at least 30 days' notice by email.`;

/** Shown above the checkout button, so nobody pays without reading it. */
export const RENEWAL_NOTE =
	"Business renews automatically every year on the same licence until you cancel. You can cancel, or change the number of people, at any time from the Stripe link we email you.";

export const CHECKOUT_NOTE =
	"Checkout is on Stripe, which asks for your name, email, payment details and how many people the licence covers. There is no account to create, and the licence is registered to that email.";

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
		body: "If a Business licence lapses, the job plugins keep running for 30 days, then new job runs stop. The app and every future version of it keep working, and every file, library and output you made stays readable.",
		icon: LaptopIcon,
	},
	{
		title: "Checked offline",
		body: "The app checks the licence file's signature on your own machine, so it works offline. An offline computer imports each year's renewed file from the email we send.",
		icon: WifiOffIcon,
	},
	{
		title: "Open source",
		body: "The app's code, the licence check included, is public on GitHub. You can read it, or build the app yourself.",
		icon: SourceCodeIcon,
	},
];

export const BUSINESS_FAQ: PricingQuestion[] = [
	FAQ_WHAT_BUSINESS_ADDS,
	FAQ_WHO_NEEDS_BUSINESS,
	FAQ_BUSINESS_RENEWAL,
	FAQ_CANCEL_OR_CHANGE,
	FAQ_BUSINESS_LAPSE,
	FAQ_BUSINESS_NO_ACCOUNT,
	FAQ_BUSINESS_TRIAL,
];
