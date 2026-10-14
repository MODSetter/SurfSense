import Link from "next/link";
import { HomeBadge } from "@/components/homepage/home/home-badge";
import { HomeButton } from "@/components/homepage/home/home-button";
import { sectionSpacing } from "@/components/homepage/home/home-section-spacing";
import { PlatformsTooltip } from "@/components/pricing/platforms-tooltip";
import {
	PLANS,
	PLUGIN_NOTE,
	type Plan,
	PRICING_FAQ,
	SELF_BUILD_URL,
	SMALL_GROUP_NOTE,
} from "@/components/pricing/pricing-content";
import { FAQJsonLd } from "@/components/seo/json-ld";
import { SiteFaqItem } from "@/components/site/site-faq-item";
import { siteText } from "@/components/site/site-text";
import { CheckIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

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
 * Pricing sections, in the homepage's shapes: centred badge heads, rounded
 * cards, no motion beyond instant hover colours.
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
		<section className={cn("text-center", sectionSpacing.head)}>
			<HomeBadge>Free forever</HomeBadge>
			<h1 className={cn(siteText.display, "mt-4")}>Pricing</h1>
			<p className={cn(siteText.lede, "mx-auto mt-8 max-w-2xl")}>
				The app and every update are <span className="text-primary">free, forever</span>, with no
				account, no trial clock and no usage cap. A licence adds the scraper plugins and priority
				support, and a 30-day one comes with the app.
			</p>
			<p className={cn(siteText.body, "mx-auto mt-5 max-w-2xl text-sm")}>
				Prefer to build it yourself?{" "}
				<a
					className={siteText.link}
					href={SELF_BUILD_URL}
					target="_blank"
					rel="noreferrer noopener"
				>
					The source is public
				</a>
				, and self-building is free too.
			</p>
		</section>
	);
}

function PlanCard({ plan }: { plan: Plan }) {
	return (
		<div
			className={cn(
				"ss-home-plan overflow-hidden rounded-3xl border bg-card shadow-xs",
				plan.featured ? "border-foreground ring-1 ring-foreground" : "border-border"
			)}
		>
			<div className="flex flex-col p-6 md:p-8">
				<p className="flex items-center justify-between gap-2">
					<span className={siteText.eyebrow}>{plan.name}</span>
					{plan.featured ? (
						<span className="rounded-full bg-foreground px-2.5 py-1 text-xs font-medium whitespace-nowrap text-background">
							Most popular
						</span>
					) : null}
				</p>

				<p className="mt-5 flex items-baseline gap-1">
					<span className="text-4xl leading-none font-semibold tracking-tight tabular-nums text-foreground md:text-5xl">
						{plan.price}
					</span>
					{plan.period ? (
						<span className={cn(siteText.body, "text-sm font-medium")}>{plan.period}</span>
					) : null}
				</p>

				{plan.note ? <p className="mt-2 text-sm font-medium text-primary">{plan.note}</p> : null}

				<p className={cn(siteText.body, "mt-3 text-sm")}>{plan.summary}</p>

				{/* At the foot of the head, which subgrid holds to one height across the
				    three cards, so the buttons line up however each summary wraps. */}
				<div className="mt-auto flex flex-col gap-2 pt-6">
					{plan.action.map((action) => (
						<HomeButton
							key={action.label}
							asChild
							size="xl"
							variant={action.primary ? "default" : "secondary"}
							className="w-full rounded-full"
						>
							{action.external ? (
								<a href={action.href} target="_blank" rel="noreferrer noopener">
									{action.label}
								</a>
							) : (
								<Link href={action.href}>{action.label}</Link>
							)}
						</HomeButton>
					))}
				</div>
			</div>

			<ul className="m-0 flex list-none flex-col gap-3 border-t border-border p-6 md:p-8">
				{plan.features.map((feature) => (
					<li key={feature} className="flex items-start gap-3 text-sm leading-relaxed">
						<span
							aria-hidden="true"
							className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-foreground text-background"
						>
							<CheckIcon className="size-3" />
						</span>
						<span className="text-muted-foreground">{renderFeature(feature)}</span>
					</li>
				))}
			</ul>
		</div>
	);
}

export function PricingPlans() {
	return (
		<section className={sectionSpacing.foot}>
			<div className="ss-home-plans mt-12 grid gap-4 md:grid-cols-3 lg:mt-16">
				{PLANS.map((plan) => (
					<PlanCard key={plan.name} plan={plan} />
				))}
			</div>

			<div className="mt-6 flex flex-col gap-4 rounded-3xl bg-muted p-6 md:p-8">
				<p className={cn(siteText.body, "text-sm")}>{PLUGIN_NOTE}</p>
				<p className={cn(siteText.body, "text-sm")}>
					{SMALL_GROUP_NOTE}{" "}
					<Link className={siteText.link} href="/contact">
						Talk to us
					</Link>
					.
				</p>
			</div>
		</section>
	);
}

/** Headed and ruled like the homepage FAQ, one flat list. */
export function PricingQuestions() {
	return (
		<section className={sectionSpacing.foot} aria-labelledby="ss-pricing-faq-label">
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>FAQ</HomeBadge>
				<h2 id="ss-pricing-faq-label" className={cn(siteText.h2, "mt-4")}>
					Questions about licences
				</h2>
			</div>

			<div className="ss-home-grid mt-10 border-t border-border lg:mt-14">
				{PRICING_FAQ.map((item) => (
					<SiteFaqItem key={item.question} question={item.question}>
						<p className={siteText.body}>{item.answer}</p>
					</SiteFaqItem>
				))}
			</div>

			<FAQJsonLd questions={PRICING_FAQ} />
		</section>
	);
}
