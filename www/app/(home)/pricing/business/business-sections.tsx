import Link from "next/link";
import { Fragment } from "react";
import { ContinueToCheckout } from "@/app/(home)/pricing/continue-to-checkout";
import { type GuideStep, GuideSteps } from "@/components/site/guide-steps";
import { HomeBadge } from "@/components/site/home-badge";
import { sectionSpacing } from "@/components/site/home-section-spacing";
import { FAQJsonLd } from "@/components/site/json-ld";
import { DOWNLOADS_URL } from "@/components/site/site-content";
import { SiteFaqItem } from "@/components/site/site-faq-item";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { CheckIcon } from "@/components/ui/icons";
import { BUSINESS_PRICE_EXAMPLES, FIRST_PERSON_PRICE, yearlyPriceLabel } from "../business-price";
import {
	BENEFITS,
	BUSINESS_FAQ,
	BUY_BUSINESS_URL,
	CHECKOUT_NOTE,
	FEATURE_REQUEST_STEPS,
	FREE_STILL_APPLIES,
	FURTHER_PEOPLE_NOTE,
	REASSURANCES,
	REFUND_NOTE,
	RENEWAL_NOTE,
} from "./business-content";

/**
 * Sections of `/pricing/business`, in `/pricing/individual`'s shapes: centred badge heads,
 * rounded cards, ruled grids. Server components; the checkout button is the only client island.
 */

const FIRST = yearlyPriceLabel(FIRST_PERSON_PRICE);

export function BusinessHero() {
	return (
		<section className={cn("text-center", sectionSpacing.head)}>
			<HomeBadge>Business licence</HomeBadge>
			<h1 className={cn(siteText.display, "mt-4")}>SurfSense Business</h1>
			<p className={cn(siteText.lede, "mx-auto mt-8 max-w-2xl")}>
				SurfSense's job plugins for your firm, the security questionnaire and the contract redline,
				priced per person. The app itself is <span className="text-primary">free either way</span>,
				and stays free.
			</p>
		</section>
	);
}

/** What a year costs for a few firm sizes, so nobody has to do the sum at checkout. */
function PriceExamples() {
	return (
		<dl className="m-0 mt-5 grid grid-cols-[1fr_auto] gap-x-4 gap-y-2 border-t border-border pt-5 text-sm">
			{BUSINESS_PRICE_EXAMPLES.map(({ people, price }) => (
				<Fragment key={people}>
					<dt className="text-muted-foreground">
						{people === 1 ? "1 person, Solo" : `${people} people`}
					</dt>
					<dd className="m-0 text-right font-medium tabular-nums text-foreground">
						{price} a year
					</dd>
				</Fragment>
			))}
		</dl>
	);
}

/** The price, the renewal and the button, in the featured card shape from `/pricing`. */
function PriceCard() {
	return (
		<aside
			aria-labelledby="ss-business-price"
			className="flex flex-col rounded-3xl border border-foreground bg-card p-6 shadow-xs ring-1 ring-foreground md:p-8 lg:sticky lg:top-24"
		>
			<p id="ss-business-price" className={siteText.eyebrow}>
				Business
			</p>
			<p className="mt-5 flex items-baseline gap-1">
				<span className="text-5xl leading-none font-semibold tracking-tight tabular-nums text-foreground">
					{FIRST}
				</span>
				<span className={cn(siteText.body, "text-sm font-medium")}>
					a year for the first person
				</span>
			</p>
			<p className="mt-3 text-sm font-medium text-primary">{FURTHER_PEOPLE_NOTE}</p>

			<PriceExamples />

			{/* Above the button: the renewal is stated before anyone pays. */}
			<p className={cn(siteText.body, "mt-5 text-sm")}>{RENEWAL_NOTE}</p>

			<div className="mt-6">
				<ContinueToCheckout buyUrl={BUY_BUSINESS_URL} plan="business" />
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

export function BusinessOffer() {
	return (
		<section className={sectionSpacing.foot} aria-labelledby="ss-business-benefits">
			<div className="mt-12 grid items-start gap-4 lg:mt-16 lg:grid-cols-5">
				<div className="lg:order-2 lg:col-span-2">
					<PriceCard />
				</div>

				<div className="overflow-hidden rounded-3xl border border-border bg-card shadow-xs lg:col-span-3">
					<h2 id="ss-business-benefits" className={cn(siteText.h3, "px-6 pt-6 md:px-8 md:pt-8")}>
						What Business unlocks
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
			aria-labelledby="ss-business-feature-request"
		>
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>Feature build request</HomeBadge>
				<h2 id="ss-business-feature-request" className={cn(siteText.h2, "mt-4")}>
					Ask for the feature your firm needs
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
		body: "Stripe asks for your name, email, payment details and how many people the licence covers. There is no account or password to create, and the licence is registered to that email.",
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
		body: "Open the app, go to Settings, then License, and add the file. It is checked on your own machine, so it works offline.",
		action: { href: "/license/activate", label: "See the activation guide" },
	},
	{
		title: "Each year, it renews",
		body: "Stripe charges the card again and the same licence is extended. An app that is allowed online fetches the renewed file itself; on an offline computer, import the file we email you.",
	},
	{
		title: "No app yet?",
		body: "Download it for Windows, macOS or Linux. The app is free, with or without a licence.",
		action: { href: DOWNLOADS_URL, label: "Go to downloads" },
	},
];

export function AfterPaying() {
	return (
		<section className={sectionSpacing.foot} aria-labelledby="ss-business-after">
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>After you pay</HomeBadge>
				<h2 id="ss-business-after" className={cn(siteText.h2, "mt-4")}>
					From checkout to your first job
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
		<section className={sectionSpacing.foot} aria-labelledby="ss-business-reassurance">
			<h2 id="ss-business-reassurance" className="sr-only">
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

export function BusinessQuestions() {
	return (
		<section className={sectionSpacing.foot} aria-labelledby="ss-business-faq">
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>FAQ</HomeBadge>
				<h2 id="ss-business-faq" className={cn(siteText.h2, "mt-4")}>
					Questions before you buy
				</h2>
			</div>
			<div className="ss-home-grid mt-10 border-t border-border lg:mt-14">
				{BUSINESS_FAQ.map((item) => (
					<SiteFaqItem key={item.question} question={item.question}>
						<p className={siteText.body}>{item.answer}</p>
					</SiteFaqItem>
				))}
			</div>
			<FAQJsonLd questions={BUSINESS_FAQ} />
		</section>
	);
}

/** The same action once more for someone who read to the end, and the trial for anyone not ready. */
export function ClosingCheckout() {
	return (
		<section className={sectionSpacing.foot} aria-labelledby="ss-business-closing">
			<div className="flex flex-col items-center rounded-4xl border border-border bg-card px-6 py-10 text-center shadow-xs md:px-12 md:py-14">
				<h2 id="ss-business-closing" className={siteText.h2}>
					{FIRST} a year for your first person
				</h2>
				<p className={cn(siteText.body, "mt-4 max-w-xl")}>
					{FURTHER_PEOPLE_NOTE} {RENEWAL_NOTE}
				</p>
				<div className="mt-8 w-full max-w-sm">
					<ContinueToCheckout buyUrl={BUY_BUSINESS_URL} plan="business" />
				</div>
				<p className={cn(siteText.body, "mt-6 text-sm")}>
					Want to try the security questionnaire and the contract redline first? The free app comes
					with a 14-day trial of both and needs no card.{" "}
					<Link className={siteText.link} href={DOWNLOADS_URL}>
						Get it on the download page
					</Link>
					.
				</p>
			</div>
		</section>
	);
}
