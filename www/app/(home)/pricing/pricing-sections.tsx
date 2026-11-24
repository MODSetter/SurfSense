import { FREE_INCLUDES, type PricingQuestion } from "@/app/(home)/pricing/pricing-content";
import { HomeBadge } from "@/components/site/home-badge";
import { sectionSpacing } from "@/components/site/home-section-spacing";
import { FAQJsonLd } from "@/components/site/json-ld";
import { SiteFaqItem } from "@/components/site/site-faq-item";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { CheckIcon } from "@/components/ui/icons";
import { HomeDownloadButton } from "@/features/downloads/home-download-button";

/**
 * Pricing sections, in the homepage's shapes: centred badge heads, rounded cards, no motion
 * beyond instant hover colours. All server components.
 *
 * There is one plan, free, so the page answers that on its first screen and then lists what
 * the free app includes.
 */

export function PricingHero() {
	return (
		<section className={cn("text-center", sectionSpacing.head)}>
			<HomeBadge>Free</HomeBadge>
			<h1 className={cn(siteText.display, "mt-4")}>Pricing</h1>
			<p className={cn(siteText.lede, "mx-auto mt-8 max-w-2xl")}>
				SurfSense is <span className="text-primary">free</span>: the app, every update and every
				job, with no licence, no account, no trial and no usage cap.
			</p>
			<div className="mt-10 flex justify-center">
				<HomeDownloadButton tone="dark" placement="pricing" />
			</div>
		</section>
	);
}

export function PricingIncludes() {
	return (
		<section className={sectionSpacing.foot} aria-labelledby="ss-pricing-includes-label">
			<div className="mx-auto mt-12 max-w-2xl overflow-hidden rounded-3xl border border-border bg-card shadow-xs lg:mt-16">
				<div className="p-6 md:p-8">
					<p id="ss-pricing-includes-label" className={siteText.eyebrow}>
						Everything, for everyone
					</p>
					<p className="mt-5 flex items-baseline gap-1">
						<span className="text-4xl leading-none font-semibold tracking-tight tabular-nums text-foreground md:text-5xl">
							$0
						</span>
					</p>
				</div>
				<ul className="m-0 flex list-none flex-col gap-3 border-t border-border p-6 md:p-8">
					{FREE_INCLUDES.map((feature) => (
						<li key={feature} className="flex items-start gap-3 text-sm leading-relaxed">
							<span
								aria-hidden="true"
								className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-foreground text-background"
							>
								<CheckIcon className="size-3" />
							</span>
							<span className="text-muted-foreground">{feature}</span>
						</li>
					))}
				</ul>
			</div>
		</section>
	);
}

/** Headed and ruled like the homepage FAQ, one flat list. */
export function PricingQuestions({ questions }: { questions: PricingQuestion[] }) {
	return (
		<section className={sectionSpacing.foot} aria-labelledby="ss-pricing-faq-label">
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>FAQ</HomeBadge>
				<h2 id="ss-pricing-faq-label" className={cn(siteText.h2, "mt-4")}>
					Common questions
				</h2>
			</div>

			<div className="ss-home-grid mt-10 border-t border-border lg:mt-14">
				{questions.map((item) => (
					<SiteFaqItem key={item.question} question={item.question}>
						<p className={siteText.body}>{item.answer}</p>
					</SiteFaqItem>
				))}
			</div>

			<FAQJsonLd questions={questions} />
		</section>
	);
}
