import { CircleCheck } from "lucide-react";
import Link from "next/link";
import { HomeButton } from "@/components/homepage/home/home-button";
import { PlatformsTooltip } from "@/components/pricing/platforms-tooltip";
import {
	ENTERPRISE_NOTE,
	PLANS,
	PLUGIN_NOTE,
	type Plan,
	PRICING_FAQ,
	SELF_BUILD_URL,
} from "@/components/pricing/pricing-content";
import { FAQJsonLd } from "@/components/seo/json-ld";

/**
 * Splits a feature string around "9 platforms" so that segment alone can be
 * wrapped in `PlatformsTooltip` — the rest of the line renders as plain text.
 */
function renderFeature(feature: string) {
	const marker = "9 platforms";
	const index = feature.indexOf(marker);
	if (index === -1) return feature;

	return (
		<>
			{feature.slice(0, index)}
			<PlatformsTooltip>{marker}</PlatformsTooltip>
			{feature.slice(index + marker.length)}
		</>
	);
}

/**
 * Pricing sections.
 *
 * Built entirely from the `ss-home-*` primitives in `app/(home)/home.css` — the
 * same ruled bands, hairline grids and native details/summary the landing page
 * uses — so the two pages read as one document rather than two designs behind a
 * shared navigation.
 *
 * All server components. The previous pricing page was a client component
 * carrying `motion`, `canvas-confetti`, `NumberFlow` and a monthly/yearly switch
 * whose two prices were identical in every tier.
 */

/**
 * The brief's first rule for this page is to lead with free: the answer to "is
 * it free?" has to be on the first screen, in plain words, before any tier
 * table. Burying it reads as a bait-and-switch to an audience that arrived via
 * the words "open source".
 */
export function PricingHero() {
	return (
		<section className="ss-home-hero ss-home-pad">
			<div className="mx-auto max-w-3xl text-center">
				<h1 className="ss-home-display">Pricing</h1>
				<p className="ss-home-lede mx-auto mt-8 max-w-2xl">
					The app and every update are <span className="ss-home-accent">free, forever</span>, with
					no account, no trial clock and no usage cap. A licence adds the scraper plugins and
					priority support.
				</p>
				<p className="ss-home-body mx-auto mt-5 max-w-2xl text-sm">
					Prefer to build it yourself?{" "}
					<a
						className="ss-home-link"
						href={SELF_BUILD_URL}
						target="_blank"
						rel="noreferrer noopener"
					>
						The source is public
					</a>
					, and self-building is free too.
				</p>
			</div>
		</section>
	);
}

function PlanCell({ plan }: { plan: Plan }) {
	return (
		<div className="ss-home-plan" data-featured={plan.featured ? "" : undefined}>
			<div className="ss-home-plan-head">
				<p className="flex items-center gap-2">
					<span className="ss-home-eyebrow">{plan.name}</span>
					{plan.featured ? <span className="ss-home-plan-badge">Most popular</span> : null}
				</p>

				<p className="mt-3 flex items-baseline gap-1">
					<span className="ss-home-price">{plan.price}</span>
					{plan.period ? (
						<span className="ss-home-body text-sm font-medium">{plan.period}</span>
					) : null}
				</p>

				{plan.note ? <p className="ss-home-plan-note mt-2">{plan.note}</p> : null}

				<p className="ss-home-body mt-2 text-sm">{plan.summary}</p>

				{/* Pushed to the foot of the head, which subgrid holds to a common
				    height across the three tiers, so the buttons sit on one line
				    however each summary wraps. */}
				<div className="mt-auto pt-6">
					<HomeButton asChild size="lg" variant={plan.featured ? "default" : "secondary"}>
						{plan.action.external ? (
							<a href={plan.action.href} target="_blank" rel="noreferrer noopener">
								{plan.action.label}
							</a>
						) : (
							<Link href={plan.action.href}>{plan.action.label}</Link>
						)}
					</HomeButton>
				</div>
			</div>

			{/* Rows are separated by their own top border rather than by a 1px grid
			    gap. A gap-drawn grid stretches its rows to fill the column, so a
			    short tier's rows would grow to match a long one's. */}
			<ul className="ss-home-plan-features">
				{plan.features.map((feature) => (
					<li key={feature}>
						<CircleCheck aria-hidden="true" className="ss-home-plan-check" />
						<span>{renderFeature(feature)}</span>
					</li>
				))}
			</ul>
		</div>
	);
}

export function PricingPlans() {
	return (
		<section className="ss-home-rule">
			<div className="ss-home-plans">
				{PLANS.map((plan) => (
					<PlanCell key={plan.name} plan={plan} />
				))}
			</div>

			<div className="ss-home-rule ss-home-pad flex flex-col gap-8 py-8">
				<p className="ss-home-body max-w-4xl text-sm">{PLUGIN_NOTE}</p>
				<p className="ss-home-body max-w-4xl text-sm">
					{ENTERPRISE_NOTE}{" "}
					<Link className="ss-home-link" href="/contact">
						Talk to us
					</Link>
					.
				</p>
			</div>
		</section>
	);
}

/**
 * One flat list, labelled once. The previous version grouped the questions under
 * five sub-headings, which put a heading between almost every pair of rows and
 * broke the ruled column into fragments.
 */
export function PricingQuestions() {
	return (
		<section className="ss-home-rule" aria-labelledby="ss-pricing-faq-label">
			<div className="ss-home-head">
				<p className="ss-home-eyebrow">FAQ</p>
				<h2 id="ss-pricing-faq-label" className="ss-home-h2 mt-2">
					Questions about <span className="ss-home-accent">licences</span>
				</h2>
			</div>

			<div className="ss-home-grid border-t border-[color:var(--border)]">
				{PRICING_FAQ.map((item) => (
					<details key={item.question} className="ss-home-faq">
						<summary className="ss-home-faq-summary">
							<span className="ss-home-h3">{item.question}</span>
							<span aria-hidden="true" className="ss-home-faq-marker" />
						</summary>
						<div className="ss-home-faq-answer">
							<p className="ss-home-body">{item.answer}</p>
						</div>
					</details>
				))}
			</div>

			<FAQJsonLd questions={PRICING_FAQ} />
		</section>
	);
}
