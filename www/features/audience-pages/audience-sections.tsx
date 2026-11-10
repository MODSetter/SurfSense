import Link from "next/link";
import type { ReactNode } from "react";
import { HomeBadge } from "@/components/site/home-badge";
import { sectionSpacing } from "@/components/site/home-section-spacing";
import { FAQJsonLd } from "@/components/site/json-ld";
import { SiteFaqItem } from "@/components/site/site-faq-item";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { ArrowRightIcon, CheckIcon, type Icon } from "@/components/ui/icons";
import { HomeDownloadButton } from "@/features/downloads/home-download-button";

/**
 * The blocks the audience and job pages are built from, in `/private-ai-for-business`'s
 * shapes: a centred hero, a badge over each section head, rounded cards, a muted split band
 * and a closing card. Server components with no client JavaScript.
 *
 * Briefs: `plans/community-local/seo/09-audience-pages.md`. Two of its rules shape these
 * blocks. Every card heading is a real H2, because the H2s carry the page's keywords, so a
 * section's own headline is a `<p>` styled like one. And the FAQ's answers stay in the
 * markup and in `FAQPage` schema from the same array, as on the homepage.
 */

export type PageLink = { label: string; href: string };

export type AudienceCard = { heading: string; body: ReactNode; icon: Icon; link?: PageLink };

export type AudienceStep = { title: string; body: ReactNode };

export type AudienceQuestion = { question: string; answer: string };

function ForwardLink({ link }: { link: PageLink }) {
	return (
		<Link className={siteText.forward} href={link.href}>
			{link.label} <ArrowRightIcon aria-hidden="true" className="size-4" />
		</Link>
	);
}

function IconTile({ icon: TileIcon }: { icon: Icon }) {
	return (
		<span
			aria-hidden="true"
			className="grid size-11 place-items-center rounded-xl bg-secondary text-foreground"
		>
			<TileIcon className="size-5" />
		</span>
	);
}

/** A centred badge over a headline that is not itself a heading. */
function SectionHead({ badge, headline }: { badge: string; headline: string }) {
	return (
		<div className={cn("text-center", sectionSpacing.head)}>
			<HomeBadge>{badge}</HomeBadge>
			<p className={cn(siteText.h2, "mt-4")}>{headline}</p>
		</div>
	);
}

export function AudienceHero({
	badge,
	title,
	highlight,
	lede,
	note,
	link,
}: {
	badge: string;
	/** The H1 up to its last words, which `highlight` draws in the accent. */
	title: string;
	highlight: string;
	/** The page's answer, in plain sentences an AI Overview can lift. */
	lede: string;
	note?: string;
	link?: PageLink;
}) {
	return (
		<section className={cn("text-center", sectionSpacing.head)}>
			<HomeBadge>{badge}</HomeBadge>
			<h1 className={cn(siteText.display, "mx-auto mt-4 max-w-4xl")}>
				{title} <span className="text-primary">{highlight}</span>
			</h1>
			<p className={cn(siteText.lede, "mx-auto mt-8 max-w-2xl")}>{lede}</p>
			{note ? <p className={cn(siteText.body, "mx-auto mt-5 max-w-2xl text-sm")}>{note}</p> : null}
			<div className="mt-10 flex flex-wrap items-center justify-center gap-x-8 gap-y-5">
				<HomeDownloadButton tone="dark" />
				{link ? <ForwardLink link={link} /> : null}
			</div>
		</section>
	);
}

/** One question answered beside a ruled list of short, checkable claims. */
export function AudienceAnswer({
	heading,
	points,
	children,
}: {
	heading: string;
	points: string[];
	/** The answer's paragraphs. */
	children: ReactNode;
}) {
	return (
		<section className={sectionSpacing.foot}>
			<div className="flex flex-col overflow-hidden rounded-3xl bg-muted p-2 lg:flex-row">
				<div className="flex flex-col justify-center p-6 md:p-10 lg:w-1/2">
					<h2 className={siteText.h2}>{heading}</h2>
					<div className={cn(siteText.body, "mt-5 flex flex-col gap-4")}>{children}</div>
				</div>

				<ul className="m-0 flex list-none flex-col justify-center gap-4 rounded-2xl bg-card p-6 md:p-10 lg:w-1/2">
					{points.map((point) => (
						<li key={point} className="flex items-center gap-3">
							<span
								aria-hidden="true"
								className="grid size-5 shrink-0 place-items-center rounded-full bg-foreground text-background"
							>
								<CheckIcon className="size-3" />
							</span>
							<span className={siteText.body}>{point}</span>
						</li>
					))}
				</ul>
			</div>
		</section>
	);
}

/** Cards whose headings are the page's H2s: two columns for an even count, three for an odd one. */
export function AudienceCards({
	badge,
	headline,
	cards,
}: {
	badge: string;
	headline: string;
	cards: AudienceCard[];
}) {
	return (
		<section className={sectionSpacing.foot}>
			<SectionHead badge={badge} headline={headline} />

			<ul
				className={cn(
					"m-0 mt-10 grid list-none gap-4 p-0 lg:mt-14",
					cards.length % 2 === 0 ? "md:grid-cols-2" : "md:grid-cols-3"
				)}
			>
				{cards.map((card) => (
					<li
						key={card.heading}
						className="flex flex-col rounded-2xl border border-border bg-card p-6 shadow-xs md:p-8"
					>
						<IconTile icon={card.icon} />
						<h2 className={cn(siteText.h3, "mt-6")}>{card.heading}</h2>
						<p className={cn(siteText.body, "mt-2 text-sm")}>{card.body}</p>
						{card.link ? (
							<p className="mt-auto pt-5">
								<ForwardLink link={card.link} />
							</p>
						) : null}
					</li>
				))}
			</ul>
		</section>
	);
}

/** A job's run, numbered, as the app walks it. Step titles are H3s under the section's H2. */
export function AudienceSteps({
	badge,
	heading,
	steps,
}: {
	badge: string;
	heading: string;
	steps: AudienceStep[];
}) {
	return (
		<section className={sectionSpacing.foot}>
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>{badge}</HomeBadge>
				<h2 className={cn(siteText.h2, "mt-4")}>{heading}</h2>
			</div>

			<ol className="m-0 mt-10 grid list-none gap-4 p-0 md:grid-cols-2 lg:mt-14 lg:grid-cols-4">
				{steps.map((step, index) => (
					<li key={step.title} className="flex flex-col rounded-3xl bg-muted p-6 md:p-8">
						<span className="grid size-8 place-items-center rounded-full bg-foreground font-mono text-xs text-background">
							{index + 1}
						</span>
						<h3 className={cn(siteText.h3, "mt-5")}>{step.title}</h3>
						<p className={cn(siteText.body, "mt-3 text-sm")}>{step.body}</p>
					</li>
				))}
			</ol>
		</section>
	);
}

/** Plain facts under one heading, such as what a job reviews and what it leaves alone. */
export function AudienceNotes({ heading, children }: { heading: string; children: ReactNode }) {
	return (
		<section className={sectionSpacing.foot}>
			<div className="rounded-3xl border border-border px-6 py-8 md:px-10 md:py-10">
				<h2 className={cn(siteText.h2, "max-w-3xl")}>{heading}</h2>
				<div className={cn(siteText.body, "mt-5 flex max-w-3xl flex-col gap-4")}>{children}</div>
			</div>
		</section>
	);
}

/** The closing card: what it costs, with the download and one more link. */
export function AudienceClosing({
	badge,
	heading,
	link,
	children,
}: {
	badge: string;
	heading: string;
	link: PageLink;
	children: ReactNode;
}) {
	return (
		<section className={sectionSpacing.foot}>
			<div className="rounded-4xl border border-border bg-card px-6 py-10 shadow-xs md:px-12 md:py-14">
				<HomeBadge>{badge}</HomeBadge>
				<h2 className={cn(siteText.h2, "mt-4 max-w-3xl")}>{heading}</h2>
				<div className={cn(siteText.body, "mt-6 flex max-w-3xl flex-col gap-4")}>{children}</div>
				<div className="mt-8 flex flex-wrap items-center gap-x-8 gap-y-5">
					<HomeDownloadButton tone="dark" />
					<ForwardLink link={link} />
				</div>
			</div>
		</section>
	);
}

export function AudienceQuestions({
	heading,
	questions,
}: {
	heading: string;
	questions: AudienceQuestion[];
}) {
	return (
		<section className={sectionSpacing.foot}>
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>FAQ</HomeBadge>
				<h2 className={cn(siteText.h2, "mt-4")}>{heading}</h2>
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
