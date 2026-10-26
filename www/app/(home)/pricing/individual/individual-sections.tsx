import Link from "next/link";
import { INDIVIDUAL_PRICE } from "@/app/(home)/pricing/pricing-content";
import { type GuideStep, GuideSteps } from "@/components/site/guide-steps";
import { HomeBadge } from "@/components/site/home-badge";
import { sectionSpacing } from "@/components/site/home-section-spacing";
import { FAQJsonLd } from "@/components/site/json-ld";
import { DOWNLOADS_URL } from "@/components/site/site-content";
import { SiteFaqItem } from "@/components/site/site-faq-item";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { CheckIcon } from "@/components/ui/icons";
import { ContinueToCheckout } from "./continue-to-checkout";
import {
	BENEFITS,
	CHECKOUT_NOTE,
	FEATURE_REQUEST_STEPS,
	FREE_STILL_APPLIES,
	INDIVIDUAL_FAQ,
	REASSURANCES,
	REFUND_NOTE,
	RENEWAL_NOTE,
} from "./individual-content";

/**
 * Sections of `/pricing/individual`, in the pricing page's shapes: centred
 * badge heads, rounded cards, ruled grids. Server components; the checkout
 * button is the only client island.
 */

export function IndividualHero() {
	return (
		<section className={cn("text-center", sectionSpacing.head)}>
			<HomeBadge>Individual licence</HomeBadge>
			<h1 className={cn(siteText.display, "mt-4")}>SurfSense Individual</h1>
			<p className={cn(siteText.lede, "mx-auto mt-8 max-w-2xl")}>
				Every SurfSense plugin, unlimited, with priority support and one feature build request a
				year. The app itself is <span className="text-primary">free either way</span>, and stays
				free.
			</p>
		</section>
	);
}

/** The price and the button, in the featured card shape from `/pricing`. */
function PriceCard() {
	return (
		<aside
			aria-labelledby="ss-individual-price"
			className="flex flex-col rounded-3xl border border-foreground bg-card p-6 shadow-xs ring-1 ring-foreground md:p-8 lg:sticky lg:top-24"
		>
			<p id="ss-individual-price" className={siteText.eyebrow}>
				Individual
			</p>
			<p className="mt-5 flex items-baseline gap-1">
				<span className="text-5xl leading-none font-semibold tracking-tight tabular-nums text-foreground">
					{INDIVIDUAL_PRICE}
				</span>
				<span className={cn(siteText.body, "text-sm font-medium")}>for the first year</span>
			</p>
			<p className="mt-3 text-sm font-medium text-primary">{RENEWAL_NOTE}</p>

			<div className="mt-6">
				<ContinueToCheckout />
			</div>

			{/* The filled tick /pricing and /private-ai-for-business use. */}
			<ul className={cn(siteText.body, "m-0 mt-5 flex list-none flex-col gap-3 p-0 text-sm")}>
				{[CHECKOUT_NOTE, REFUND_NOTE].map((note) => (
					<li key={note} className="flex items-start gap-3">
						<span
							aria-hidden="true"
							className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-foreground text-background"
						>
							<CheckIcon className="size-3" />
						</span>
						<span>{note}</span>
					</li>
				))}
			</ul>
		</aside>
	);
}

export function IndividualOffer() {
	return (
		<section className={sectionSpacing.foot} aria-labelledby="ss-individual-benefits">
			<div className="mt-12 grid items-start gap-4 lg:mt-16 lg:grid-cols-5">
				<div className="lg:order-2 lg:col-span-2">
					<PriceCard />
				</div>

				<div className="overflow-hidden rounded-3xl border border-border bg-card shadow-xs lg:col-span-3">
					<h2 id="ss-individual-benefits" className={cn(siteText.h3, "px-6 pt-6 md:px-8 md:pt-8")}>
						What the licence unlocks
					</h2>
					<ul className="m-0 flex list-none flex-col gap-6 p-6 md:p-8">
						{BENEFITS.map((benefit) => (
							<li key={benefit.title} className="flex items-start gap-4">
								<span
									aria-hidden="true"
									className="grid size-10 shrink-0 place-items-center rounded-full bg-muted text-foreground"
								>
									<benefit.icon className="size-5" />
								</span>
								<div>
									<h3 className="font-medium text-foreground">{benefit.title}</h3>
									<p className={cn(siteText.body, "mt-1 text-sm")}>{benefit.body}</p>
								</div>
							</li>
						))}
					</ul>
					<p className={cn(siteText.body, "border-t border-border p-6 text-sm md:px-8")}>
						{FREE_STILL_APPLIES}
					</p>
				</div>
			</div>
		</section>
	);
}

export function FeatureRequestTerms() {
	return (
		<section
			id="feature-request"
			className={cn("scroll-mt-24", sectionSpacing.foot)}
			aria-labelledby="ss-feature-request"
		>
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>Feature build request</HomeBadge>
				<h2 id="ss-feature-request" className={cn(siteText.h2, "mt-4")}>
					Ask for the feature you need
				</h2>
			</div>
			<ol className="ss-home-grid m-0 mt-10 list-none overflow-hidden rounded-3xl border border-border p-0 md:grid-cols-2 lg:mt-14">
				{FEATURE_REQUEST_STEPS.map((step, index) => (
					<li key={step} className="flex gap-4 p-6 md:p-8">
						<span className="grid size-8 shrink-0 place-items-center rounded-full bg-foreground font-mono text-xs text-background">
							{index + 1}
						</span>
						<p className={siteText.body}>{step}</p>
					</li>
				))}
			</ol>
		</section>
	);
}

const AFTER_PAYING: GuideStep[] = [
	{
		title: "Pay on Stripe",
		body: "Stripe asks for your name, email and payment details. There is no account or password to create, and the licence is registered to that email.",
	},
	{
		title: "Save your licence file",
		body: (
			<>
				The confirmation page downloads it as <code className="font-mono">surfsense.lic</code>, and
				a copy is emailed to you. Lose it later and it can be emailed again.
			</>
		),
	},
	{
		title: "Import it in SurfSense",
		body: "Open the app, go to Settings, then License, and add the file. It is checked on your own machine, so it works offline and on every computer you install SurfSense on.",
		action: { href: "/license/activate", label: "See the activation guide" },
	},
	{
		title: "No app yet?",
		body: "Download it for Windows, macOS or Linux. The app is free, with or without a licence.",
		action: { href: DOWNLOADS_URL, label: "Go to downloads" },
	},
];

export function AfterPaying() {
	return (
		<section className={sectionSpacing.foot} aria-labelledby="ss-individual-after">
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>After you pay</HomeBadge>
				<h2 id="ss-individual-after" className={cn(siteText.h2, "mt-4")}>
					From checkout to unlocked plugins
				</h2>
			</div>
			<div className="mt-10 lg:mt-14">
				<GuideSteps steps={AFTER_PAYING} />
			</div>
		</section>
	);
}

export function Reassurances() {
	return (
		<section className={sectionSpacing.foot} aria-labelledby="ss-individual-reassurance">
			<h2 id="ss-individual-reassurance" className="sr-only">
				Before you buy
			</h2>
			<ul className="ss-home-grid m-0 list-none overflow-hidden rounded-3xl border border-border p-0 md:grid-cols-2 lg:grid-cols-4">
				{REASSURANCES.map((item) => (
					<li key={item.title} className="flex flex-col p-6 md:p-8">
						<item.icon aria-hidden="true" className="size-6 text-foreground" />
						<h3 className={cn(siteText.h3, "mt-4")}>{item.title}</h3>
						<p className={cn(siteText.body, "mt-2 text-sm")}>{item.body}</p>
					</li>
				))}
			</ul>
		</section>
	);
}

export function IndividualQuestions() {
	return (
		<section className={sectionSpacing.foot} aria-labelledby="ss-individual-faq">
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>FAQ</HomeBadge>
				<h2 id="ss-individual-faq" className={cn(siteText.h2, "mt-4")}>
					Questions before you buy
				</h2>
			</div>
			<div className="ss-home-grid mt-10 border-t border-border lg:mt-14">
				{INDIVIDUAL_FAQ.map((item) => (
					<SiteFaqItem key={item.question} question={item.question}>
						<p className={siteText.body}>{item.answer}</p>
					</SiteFaqItem>
				))}
			</div>
			<FAQJsonLd questions={INDIVIDUAL_FAQ} />
		</section>
	);
}

/** The same action once more for someone who read to the end, and the free route for anyone not ready. */
export function ClosingCheckout() {
	return (
		<section className={sectionSpacing.foot} aria-labelledby="ss-individual-closing">
			<div className="flex flex-col items-center rounded-4xl border border-border bg-card px-6 py-10 text-center shadow-xs md:px-12 md:py-14">
				<h2 id="ss-individual-closing" className={siteText.h2}>
					{INDIVIDUAL_PRICE} for your first year
				</h2>
				<p className={cn(siteText.body, "mt-4 max-w-xl")}>{RENEWAL_NOTE}</p>
				<div className="mt-8 w-full max-w-sm">
					<ContinueToCheckout />
				</div>
				<p className={cn(siteText.body, "mt-6 text-sm")}>
					Want to try the plugins first? The free plan comes with a 14-day licence and needs no
					card.{" "}
					<Link className={siteText.link} href={DOWNLOADS_URL}>
						Get it on the download page
					</Link>
					.
				</p>
			</div>
		</section>
	);
}
