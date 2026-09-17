import { DOWNLOADS_URL, REPO_URL } from "@/components/site/site-content";

/**
 * Pricing copy.
 *
 * Sourced from `plans/community-local/`:
 *   - tiers and figures: `00d-pivot-plan.md` ("Pricing", line 50) and its
 *     licensing, plugin and trial sections
 *   - title, meta, H1 and the lead-with-free rule: `seo/02-page-briefs.md`
 *     (`/pricing` — B5)
 *
 * Two things the brief asks for are deliberately absent, because inventing them
 * would be worse than omitting them:
 *
 *   - **The early-bird end date.** The plan fixes it at launch + 30 days, and
 *     launch day is not set (`portal/02-pages.md`). The copy states the window,
 *     not a date.
 *   - **The six NotebookLM comparison H2s.** Each must open with a factual,
 *     dated answer about Google's tiers, prices and source limits, and no
 *     document in `plans/` carries those numbers. The brief is explicit about
 *     this case: "If that is more than the pricing page should carry, move the
 *     comparison to a blog post and link it; do not fake it."
 *
 * Individual's primary button is the Stripe Payment Link in
 * `NEXT_PUBLIC_STRIPE_LICENSE_INDIVIDUAL_URL`. Empty falls back to `/contact`.
 * The trial button stays on `/license`.
 */

export const LICENSE_URL = "/license";
export const BUY_INDIVIDUAL_URL =
	process.env.NEXT_PUBLIC_STRIPE_LICENSE_INDIVIDUAL_URL || "/contact";

/**
 * The nine scraper platforms behind the "9 platforms" feature line, in the
 * same order as the `PLUGINS` list on `/plugins` (`app/(home)/plugins/page.tsx`),
 * minus the web crawler — that one is called out separately in the copy
 * ("9 platforms and the web crawler") and in this list's consumer.
 */
export const PLUGIN_PLATFORMS = [
	"Reddit",
	"YouTube",
	"Instagram",
	"TikTok",
	"Google Maps",
	"Google Search",
	"Indeed",
	"Amazon",
	"Walmart",
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
		summary: "The app and every update, forever. No account, no expiry.",
		features: [
			"The full app on Windows, macOS and Linux",
			"Runs offline; your sources stay on your disk",
			"Bring your own model keys, or run a local model",
			"Open source, so you can build it yourself",
		],
		action: [{ label: "Download", href: DOWNLOADS_URL }],
	},
	{
		name: "Individual",
		price: "$120",
		period: "/year",
		note: "$60 for the first 30 days",
		summary: "Adds the scraper plugins and priority support for one person.",
		features: [
			"Everything in Free",
			"Every scraper plugin: 9 platforms and the web crawler",
			"Flat-included and unlimited, with no per-item metering",
			"Priority support",
		],
		action: [
			{ label: "Buy a licence", href: BUY_INDIVIDUAL_URL, external: true, primary: true },
			{ label: "Start a 30-day trial", href: LICENSE_URL },
		],
		featured: true,
	},
	{
		name: "Team",
		price: "$80",
		period: "/seat/year",
		note: "5 to 25 seats, self-serve",
		summary: "The same licence for a group, delivered as one shared key.",
		features: [
			"Everything in Individual",
			"One key for the whole team",
			"Add seats without redistributing files",
			"SSO, SAML and on-prem hosting available",
		],
		action: [{ label: "Get a team licence", href: "/contact" }],
	},
];

/** Enterprise is a fourth tier, but it is invoiced rather than self-serve, so it
 *  reads as a line under the table instead of a card nobody can buy. */
export const ENTERPRISE_NOTE =
	"Enterprise is $80 per seat per year with a $3,000 minimum, invoiced. Sandboxed artifact generation, SSO and SAML, an on-prem licence and plugin mirror for zero-egress networks, and a local egress audit log are on the roadmap.";

/** Required by the brief: buyers must know the first plugin is not in the box. */
export const PLUGIN_NOTE =
	"No plugin ships in version 2.0. The first one is the hosted scraper API, covering all nine platforms and the web crawler, and it arrives the week after launch as 2.1, through auto-update.";

/**
 * Answers are written as quotable definitions: one plain paragraph an AI
 * Overview or a People Also Ask box can lift verbatim. The questions come from
 * the pricing intercept cluster in `seo/02-page-briefs.md`, narrowed to the ones
 * that can be answered about our own product without asserting anything about
 * Google's current tiers.
 */
export const PRICING_FAQ = [
	{
		question: "Is SurfSense free?",
		answer:
			"Yes. The app and all of its updates are free forever, with no account, no trial clock and no usage cap. You download it, install it, and use it. A paid licence is only needed for the scraper plugins and priority support; everything the app itself does stays free.",
	},
	{
		question: "What does a paid licence actually add?",
		answer:
			"A licence unlocks priority support and the scraper plugins: nine platform connectors plus the web crawler. Plugins are flat-included and unlimited, so there is no per-item metering and no credit balance to top up. The app's own features are not gated behind it.",
	},
	{
		question: "Is there a free trial?",
		answer:
			"Yes. The trial runs 30 days and needs only an email address, with no card and no account. You receive a licence file by email, drop it into the app, and every plugin is unlocked for the trial period.",
	},
	{
		question: "What happens when my licence expires?",
		answer:
			"The app keeps working. A licence expiry never disables SurfSense: your documents, your index and every local feature carry on exactly as before. Only the scraper plugins stop, because they are the part that runs against our servers. Renewing is a new licence file.",
	},
	{
		question: "Do I need an account to buy?",
		answer:
			"No. There is no account anywhere in the purchase flow. Checkout collects an email address, the licence file is sent to it and also offered on the confirmation page, and you can have it resent to that same address at any time.",
	},
	{
		question: "Can I run NotebookLM locally?",
		answer:
			"No. NotebookLM is a Google cloud service: it requires a Google account, uploads your sources to Google's servers, and cannot be installed on your own machine. Running the same workflow locally means using an alternative built for it, such as SurfSense, which keeps sources and answers on your computer.",
	},
];

export const SELF_BUILD_URL = REPO_URL;
