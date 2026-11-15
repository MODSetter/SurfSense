import { REPO_URL } from "@/components/site/site-content";

/**
 * What the pricing pages share: the shapes of a plan, the lede and a question, the feature
 * build request's line, the NotebookLM question and the link to build the app yourself.
 *
 * The copy is `business-pricing-content.ts` for `/pricing` and `business/business-content.ts`
 * for `/pricing/business`. The Individual licence and its page retired when Business went on
 * sale, and `/pricing/individual` redirects to `/pricing/business`.
 *
 * Two things the `/pricing` brief (`plans/community-local/seo/02-page-briefs.md`, B5) asks
 * for are deliberately absent, because inventing them would be worse than omitting them:
 *
 *   - **An early-bird end date.** The price names no window rather than one that has passed.
 *   - **The six NotebookLM comparison H2s.** Each must open with a factual, dated answer about
 *     Google's tiers, prices and source limits, and no document in `plans/` carries those
 *     numbers. The brief is explicit about this case: "If that is more than the pricing page
 *     should carry, move the comparison to a blog post and link it; do not fake it."
 */

export const FEATURE_REQUEST_LINE = "1 feature build request a year";

export type Plan = {
	name: string;
	price: string;
	period?: string;
	note?: string;
	summary: string;
	features: string[];
	action: { label: string; href: string; external?: boolean; primary?: boolean }[];
	featured?: boolean;
	/** The featured card's pill; "Most popular" when unset. */
	badge?: string;
};

/** The hero's lede, with its one highlighted phrase. */
export type PricingLede = { before: string; highlight: string; after: string };

/**
 * Answers are written as quotable definitions: one plain paragraph an AI
 * Overview or a People Also Ask box can lift verbatim. The questions come from
 * the pricing intercept cluster in `seo/02-page-briefs.md`, narrowed to the ones
 * that can be answered about our own product without asserting anything about
 * Google's current tiers.
 */
export type PricingQuestion = { question: string; answer: string };

export const FAQ_NOTEBOOKLM_LOCALLY: PricingQuestion = {
	question: "Can I run NotebookLM locally?",
	answer:
		"No. NotebookLM is a Google cloud service: it requires a Google account, uploads your sources to Google's servers, and cannot be installed on your own machine. Running the same workflow locally means using an alternative built for it, such as SurfSense, which keeps sources and answers on your computer.",
};

export const SELF_BUILD_URL = REPO_URL;
