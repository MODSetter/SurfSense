import { DOWNLOADS_URL, REPO_URL } from "@/components/site/site-content";

/**
 * Pricing copy.
 *
 * Sourced from `plans/community-local/`:
 *   - tiers and figures: `00d-pivot-plan.md` ("Pricing") and its
 *     licensing and trial sections
 *   - title, meta, H1 and the lead-with-free rule: `seo/02-page-briefs.md`
 *     (`/pricing` — B5)
 *
 * The plugin note follows `docs/adr/0025-scraper-client-as-paid-plugin.md`,
 * which supersedes the plan's plugin section.
 *
 * Three things here disagree with the plan documents, all decided after those
 * documents were written:
 *
 *   - **The licence is 30 days, not the 14 the plan still says.**
 *     `LICENSE_TRIAL_DAYS` defaults to 30 in `app/config/__init__.py` and in
 *     both `.env.example` files, and it is what sets the expiry and the wording
 *     of the licence email.
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
 *   - **The early-bird end date.** The plan fixes it at launch + 30 days.
 *     Launch was 18 Sep 2026, so that is 18 Oct 2026; the copy has not been
 *     updated to state it and still gives the window.
 *   - **The six NotebookLM comparison H2s.** Each must open with a factual,
 *     dated answer about Google's tiers, prices and source limits, and no
 *     document in `plans/` carries those numbers. The brief is explicit about
 *     this case: "If that is more than the pricing page should carry, move the
 *     comparison to a blog post and link it; do not fake it."
 *
 * Individual's primary button is the Stripe Payment Link in
 * `NEXT_PUBLIC_STRIPE_LICENSE_INDIVIDUAL_URL`. Empty falls back to `/contact`.
 *
 * Free has one button, to `/downloads`, and not a second one to `/license` for
 * the 30-day licence: that licence is claimed by email on `/downloads` itself,
 * and a licence file is inert without the app anyway. `/license` is where
 * someone who already has a licence gets the file back.
 */

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
		note: "Includes a 30-day licence, no card",
		summary: "The app and every update, forever. No account, no expiry.",
		features: [
			"The full app on Windows, macOS and Linux",
			"Runs offline; your sources stay on your disk",
			"Bring your own model keys, or run a local model",
			"A 30-day licence for the plugins, sent by email",
			"Open source, so you can build it yourself",
		],
		action: [{ label: "Download", href: DOWNLOADS_URL }],
	},
	{
		name: "Individual",
		price: "$60",
		period: "/year",
		note: "First year, then $120.",
		summary: "Adds the scraper plugins and priority support for one person.",
		features: [
			"Everything in Free",
			"Every scraper plugin: 9 platforms and the web crawler",
			"Unlimited, with no per-item metering and no credits to buy",
			"Priority support",
		],
		action: [{ label: "Buy a licence", href: BUY_INDIVIDUAL_URL, external: true, primary: true }],
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
 * Removing the Team tier leaves a gap at five to twenty-five people, and this
 * line fills it with the answer that needs no product: buy that many Individual
 * licences. At $120 each that is more per person than the $80 seat it replaces,
 * and the trade is deliberate — nobody manages a seat count, nobody sits a
 * sales call, and the licence file already works this way, so the path needs
 * no code at all.
 */
export const SMALL_GROUP_NOTE =
	"A handful of people do not need an enterprise agreement. Buy an Individual licence each: there is no minimum, no seat count to manage, and everyone gets their own file. Enterprise is about how you deploy SurfSense, not how many people use it.";

/** Required by the brief: buyers must know the first plugin is not in the box. */
export const PLUGIN_NOTE =
	"No plugin ships in version 2.0. The first one will be the hosted scraper API, covering all nine platforms and the web crawler, installed from inside the app once the plugin system is ready.";

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
		question: "What does a paid licence add?",
		answer:
			"A licence unlocks priority support and the scraper plugins: nine platform connectors plus the web crawler. Plugins are unlimited at a flat price, so nothing is metered per item and there is no credit balance to top up. The licence does not lock any of the app's own features.",
	},
	{
		question: "Is there a free trial?",
		answer:
			"Yes. A 30-day licence comes with the free plan. It needs only an email address, with no card and no account. You receive a licence file by email, drop it into the app, and every plugin is unlocked for 30 days. The clock starts when the first plugin ships rather than when you ask for the file, so waiting for it costs you nothing.",
	},
	{
		question: "Does the $60 early-bird price renew at $60?",
		answer:
			"No. The $60 covers the first year; it renews at the $120 list price. The early-bird window itself is open for 30 days after launch, so $60 is the first-year price for anyone who buys inside it. Enterprise agreements are priced separately.",
	},
	{
		question: "What do you offer enterprises?",
		answer:
			"Enterprise is a deployment, not a bigger plan. It covers running SurfSense with no egress at all, with licensing and the plugin endpoints mirrored inside your own network. It also covers model and network policy you set centrally, a local audit log of outbound calls, installers your IT rolls out on a version you pin, connectors for your internal systems, and named support on an agreed response time. Pricing comes out of a conversation and is invoiced annually against a contract. Google's comparable product, NotebookLM Enterprise, publishes no price either, and is sold through Google Cloud in subscriptions of 15 to 5,000 licences.",
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
