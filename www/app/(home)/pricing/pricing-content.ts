import { DOWNLOADS_URL, EMAIL, REPO_URL } from "@/components/site/site-content";

/**
 * Pricing copy.
 *
 * Sourced from `plans/community-local/`:
 *   - tiers and figures: `00d-pivot-plan.md` ("Pricing") and its
 *     licensing and trial sections
 *   - title, meta, H1 and the lead-with-free rule: `seo/02-page-briefs.md`
 *     (`/pricing` — B5)
 *
 * The plugin copy follows `docs/adr/0025-scraper-client-as-paid-plugin.md`,
 * which supersedes the plan's plugin section. SurfSense's plugins shipped in
 * 2.2.1 as eight MCP servers on the plugin host; the platform list below
 * follows the app's first-party list
 * (`surfsense_local/backend/modules/plugins/lists/first_party/plugins.json`).
 *
 * The trial licence is 14 days, as the plan says: `LICENSE_TRIAL_DAYS` in
 * `backend/license/settings.py` sets the expiry and the wording of the licence
 * email.
 *
 * Two things here disagree with the plan documents, both decided after those
 * documents were written:
 *
 *   - **Individual shows $60, the early-bird price**, because that is what a
 *     buyer pays today. It covers the first year and renews at the $120 list
 *     price.
 *   - **Team and Enterprise are one tier, and it is not sold by the seat.**
 *     The plan's $80/seat Team and its $3,000-minimum Enterprise sold the same
 *     licence file two ways: `maxUsers` is informational rather than enforced
 *     (`contracts/01-license-file.md`), and there is no `enterprise` plan value
 *     at all — only an `enterprise` issue *source*, which
 *     `scripts/issue_enterprise_license.py` uses to mint a team licence. So a
 *     seat count was never the thing being bought. Enterprise is now priced per
 *     deployment and quoted, which is also what every comparable vendor does:
 *     AnythingLLM, Open WebUI and Google all publish no enterprise price, and
 *     Msty is the one exception at $300 per user per year (Sep 2026).
 *
 * Two things the brief asks for are deliberately absent, because inventing them
 * would be worse than omitting them:
 *
 *   - **The early-bird end date.** The plan put it at launch + 30 days,
 *     18 Oct 2026, yet $60 is still the price the maintainer set on 21 Oct
 *     2026, so the copy names no window rather than one that has passed.
 *   - **The six NotebookLM comparison H2s.** Each must open with a factual,
 *     dated answer about Google's tiers, prices and source limits, and no
 *     document in `plans/` carries those numbers. The brief is explicit about
 *     this case: "If that is more than the pricing page should carry, move the
 *     comparison to a blog post and link it; do not fake it."
 *
 * Individual's primary button goes to `/pricing/individual`, which says what
 * the licence is before handing over to the Stripe Payment Link in
 * `NEXT_PUBLIC_STRIPE_LICENSE_INDIVIDUAL_URL`. Empty falls back to `/contact`.
 *
 * The Payment Link is a one-off payment, not a subscription: fulfilment
 * (`backend/license/purchase.py`) handles only a paid checkout
 * session, so a recurring charge would never yield a new file. Renewal is a
 * new licence at the list price.
 *
 * Free has one button, to `/downloads`, and not a second one to `/license` for
 * the 14-day licence: that licence is claimed by email on `/downloads` itself,
 * and a licence file is inert without the app anyway. `/license` is where
 * someone who already has a licence gets the file back.
 */

export const BUY_INDIVIDUAL_URL =
	process.env.NEXT_PUBLIC_STRIPE_LICENSE_INDIVIDUAL_URL || "/contact";

/** The checkout landing page Individual's buttons lead to. */
export const INDIVIDUAL_CHECKOUT_URL = "/pricing/individual";

export const INDIVIDUAL_PRICE = "$60";
export const INDIVIDUAL_LIST_PRICE = "$120";

/** Decided by the maintainer on 21 Oct 2026; terms section 5 carries the same rules. */
export const FEATURE_REQUEST_LINE = "1 feature build request a year";

/**
 * The seven platforms behind the "7 platforms" feature line, in the same order
 * as the `PLUGINS` list on `/plugins` (`app/(home)/plugins/page.tsx`), minus the
 * web crawler — that one is called out separately in the copy ("7 platforms and
 * the web crawler") and in this list's consumer. Reddit and Instagram are not
 * offered: both close their public pages to readers who are not signed in.
 */
export const PLUGIN_PLATFORMS = [
	"Google Search",
	"YouTube",
	"TikTok",
	"Google Maps",
	"Amazon",
	"Walmart",
	"Indeed",
];

export type Plan = {
	name: string;
	price: string;
	period?: string;
	note?: string;
	summary: string;
	features: string[];
	action: { label: string; href: string; external?: boolean; primary?: boolean }[];
	featured?: boolean;
};

export const PLANS: Plan[] = [
	{
		name: "Free",
		price: "$0",
		note: "Includes a 14-day licence, no card",
		summary: "The app and every update, forever. No account, no expiry.",
		features: [
			"The full app on Windows, macOS and Linux",
			"Runs offline; your sources stay on your disk",
			"Bring your own model keys, or run a local model",
			"A 14-day licence for the plugins, sent by email",
			"Open source, so you can build it yourself",
		],
		action: [{ label: "Download", href: DOWNLOADS_URL }],
	},
	{
		name: "Individual",
		price: INDIVIDUAL_PRICE,
		period: "/year",
		note: `First year, then ${INDIVIDUAL_LIST_PRICE}.`,
		summary: "Adds the scraper plugins and priority support for one person.",
		features: [
			"Everything in Free",
			"Every SurfSense plugin: 7 platforms and the web crawler",
			"Unlimited, with no per-item metering and no credits to buy",
			"Priority support",
			FEATURE_REQUEST_LINE,
		],
		action: [{ label: "Buy a licence", href: INDIVIDUAL_CHECKOUT_URL, primary: true }],
		featured: true,
	},
	{
		name: "Enterprise",
		price: "Custom",
		note: "Annual, invoiced",
		summary: "The same app, run inside your own network and bought on a contract.",
		features: [
			"Everything in Individual, for everyone",
			"No egress at all: licensing and plugins mirrored inside your network",
			"You decide which models and destinations everyone can reach",
			"A local audit log of every outbound call",
			"Installers your IT rolls out, pinned to a version you choose",
			"Connectors built for your internal systems",
			"Named support on an agreed response time",
		],
		action: [{ label: "Talk to us", href: "/contact" }],
	},
];

/**
 * Answers are written as quotable definitions: one plain paragraph an AI
 * Overview or a People Also Ask box can lift verbatim. The questions come from
 * the pricing intercept cluster in `seo/02-page-briefs.md`, narrowed to the ones
 * that can be answered about our own product without asserting anything about
 * Google's current tiers.
 */
export type PricingQuestion = { question: string; answer: string };

export const FAQ_IS_IT_FREE: PricingQuestion = {
	question: "Is SurfSense free?",
	answer:
		"Yes. The app and all of its updates are free forever, with no account, no trial clock and no usage cap. You download it, install it, and use it. A paid licence is only needed for the scraper plugins and priority support; everything the app itself does stays free.",
};

export const FAQ_WHAT_A_LICENCE_ADDS: PricingQuestion = {
	question: "What does a paid licence add?",
	answer:
		"A licence unlocks priority support and SurfSense's own plugins: Google Search, YouTube, TikTok, Google Maps, Amazon, Walmart and Indeed, plus the web crawler. Plugins are unlimited at a flat price, so nothing is metered per item and there is no credit balance to top up. A paid Individual licence also includes one feature build request a year. The licence does not lock any of the app's own features, and third-party plugins and MCP servers you add yourself need no licence.",
};

export const FAQ_FEATURE_REQUEST: PricingQuestion = {
	question: "What is a feature build request?",
	answer: `A paid Individual licence includes one feature build request per licence year. You email it to ${EMAIL} from the address the licence is registered to, and we reply within 5 business days with yes or no and the scope we would build. If it fits about a week of engineering work and the direction of the product, it goes to the top of the queue and ships in the open-source app for everyone. There is no fixed delivery date, and if we decline a request you can send another one instead.`,
};

export const FAQ_FREE_TRIAL: PricingQuestion = {
	question: "Is there a free trial?",
	answer:
		"Yes. A 14-day licence comes with the free plan. It needs only an email address, with no card and no account. You enter your email on the download page, receive a licence file, import it in Settings › License, and every SurfSense plugin is unlocked for 14 days.",
};

export const FAQ_RENEWAL: PricingQuestion = {
	question: "Does the $60 early-bird price renew at $60?",
	answer:
		"No. The $60 covers the first year, and a licence after that is $120 a year, the list price. It is a single payment, not a subscription, so nothing is charged again on its own: renewing is a new licence file. Enterprise agreements are priced separately.",
};

const FAQ_ENTERPRISE: PricingQuestion = {
	question: "What do you offer enterprises?",
	answer:
		"Enterprise is a deployment, not a bigger plan. It covers running SurfSense with no egress at all, with licensing and the plugin endpoints mirrored inside your own network. It also covers model and network policy you set centrally, a local audit log of outbound calls, installers your IT rolls out on a version you pin, connectors for your internal systems, and named support on an agreed response time. Pricing comes out of a conversation and is invoiced annually against a contract. Google's comparable product, NotebookLM Enterprise, publishes no price either, and is sold through Google Cloud in subscriptions of 15 to 5,000 licences.",
};

export const FAQ_EXPIRY: PricingQuestion = {
	question: "What happens when my licence expires?",
	answer:
		"The app keeps working. A licence expiry never disables SurfSense: your documents, your index and every local feature carry on exactly as before. Only SurfSense's own plugins stop, because they run on our servers; third-party plugins keep working. Renewing is a new licence file.",
};

export const FAQ_NO_ACCOUNT: PricingQuestion = {
	question: "Do I need an account to buy?",
	answer:
		"No. There is no account anywhere in the purchase flow. Checkout collects an email address, the licence file is sent to it and also offered on the confirmation page, and you can have it resent to that same address at any time.",
};

const FAQ_NOTEBOOKLM_LOCALLY: PricingQuestion = {
	question: "Can I run NotebookLM locally?",
	answer:
		"No. NotebookLM is a Google cloud service: it requires a Google account, uploads your sources to Google's servers, and cannot be installed on your own machine. Running the same workflow locally means using an alternative built for it, such as SurfSense, which keeps sources and answers on your computer.",
};

export const PRICING_FAQ: PricingQuestion[] = [
	FAQ_IS_IT_FREE,
	FAQ_WHAT_A_LICENCE_ADDS,
	FAQ_FEATURE_REQUEST,
	FAQ_FREE_TRIAL,
	FAQ_RENEWAL,
	FAQ_ENTERPRISE,
	FAQ_EXPIRY,
	FAQ_NO_ACCOUNT,
	FAQ_NOTEBOOKLM_LOCALLY,
];

export const SELF_BUILD_URL = REPO_URL;
