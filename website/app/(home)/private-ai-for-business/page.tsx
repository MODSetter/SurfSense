import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { HomeBadge } from "@/components/homepage/home/home-badge";
import { HomeDownloadButton } from "@/components/homepage/home/home-download-button";
import { sectionSpacing } from "@/components/homepage/home/home-section-spacing";
import { siteText } from "@/components/site/site-text";
import {
	Agreement01Icon,
	ArrowRightIcon,
	Briefcase01Icon,
	Calculator01Icon,
	ChartHistogramIcon,
	CheckIcon,
	File02Icon,
	Pdf01Icon,
	PodcastIcon,
	Presentation02Icon,
} from "@/components/ui/icons";
import { cn } from "@/lib/utils";

/**
 * Confidential documents into deliverables — the cross-cutting professional page.
 *
 * Build sheet: `plans/community-local/seo/02-page-briefs.md`, "Confidential
 * documents into deliverables". It exists because the hosted product's own chat
 * logs disagree with the rest of the page plan about who the reader is: among
 * users who state a task, professional work outruns study by about 1.8 to 1 and
 * the most common single job is turning a document already on disk into a deck,
 * a report or a briefing (`plans/community-local/seo/07-what-users-do.md`).
 *
 * Three rules from the brief that constrain edits here:
 *
 * - **It cannot be titled for the job.** `pdf to presentation` is 110 searches a
 *   month and `document to presentation` is 10 — nobody searches for the
 *   mechanic. The title carries `private ai for business` and the professions
 *   instead.
 * - **It is not a vertical page and must not become ten of them.** Legal,
 *   accounting and consulting are H2s inside this one page; vertical pages would
 *   each need their own legal review for compliance-adjacent copy.
 * - **Say where the bytes are, not what regulation that satisfies.** "HIPAA
 *   compliant" and "GDPR compliant" are claims about the deployer's controls,
 *   not properties software carries on its own. The closing section states what
 *   is architecturally true and lets the reader draw the conclusion.
 *
 * Terms the brief flags as two months old — `secure ai for business`,
 * `ai for professional services`, `ai for consultants` — are deliberately not in
 * body copy. Re-pull them before they earn any.
 *
 * A server component with no client JavaScript, in the homepage's shapes:
 * centred badge heads, rounded cards and banners. The chrome comes from
 * `app/(home)/layout.tsx`.
 */

const canonicalUrl = "https://www.surfsense.com/private-ai-for-business";

/**
 * 58 characters, inside the brief's 60-character budget. The brief writes the
 * separator as an em dash; no shipped title or body string on this site uses
 * one, so it takes the colon that `/pricing` and `/mcp-server` already use.
 */
const metaTitle = "Private AI for Business: Documents Never Leave Your Laptop";
const metaDescription =
	"Turn confidential documents into decks, reports and briefings on your own machine. Nothing is uploaded, so there is no vendor copy to subpoena.";

export const metadata: Metadata = {
	title: metaTitle,
	description: metaDescription,
	// Only the terms with three or more months of history behind them; the
	// brief's four candidate rows are held back pending a re-pull.
	keywords: [
		"private ai for business",
		"ai workspace",
		"ai knowledge base",
		"ai for lawyers",
		"ai for accountants",
		"ai contract review",
		"ai for compliance",
	],
	alternates: { canonical: canonicalUrl },
	openGraph: {
		title: metaTitle,
		description: metaDescription,
		url: canonicalUrl,
		siteName: "SurfSense",
		type: "website",
		images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Private AI for business" }],
	},
	twitter: {
		card: "summary_large_image",
		title: metaTitle,
		description: metaDescription,
		images: ["/og-image.png"],
	},
};

/**
 * The professions, as H2s. Three, not ten, and each names a real artefact from
 * that profession rather than reading as a landing page in miniature.
 *
 * Engineering is the fourth-largest domain in the production-chat read but is
 * named in the lede rather than given a cell — the brief specifies these three.
 */
const PROFESSIONS: { heading: string; body: string; icon: ReactNode }[] = [
	{
		heading: "For lawyers and legal teams",
		icon: <Agreement01Icon className="size-5" />,
		body: "Point it at a discovery folder and get an indexed evidence bundle, a chronology or a client letter back. Contract review runs against the executed copy sitting on your disk, and because nothing was sent to a vendor there is no third-party custodian holding it and no retention policy to read.",
	},
	{
		heading: "For accountants and auditors",
		icon: <Calculator01Icon className="size-5" />,
		body: "Add the statements, the ledger export and last year's working file, and get a reconciliation summary, a variance note or a board pack back. Client figures stay in the folder they arrived in and nowhere else.",
	},
	{
		heading: "For consultants and analysts",
		icon: <Briefcase01Icon className="size-5" />,
		body: "Turn a research folder into a client-ready deck, a findings report or a short briefing. Material under NDA never reaches a model you do not control, because you pick the model and it can be one running on the same laptop.",
	},
];

/**
 * What comes out. One H2 per output, per the brief.
 *
 * These will link the format feature pages when those exist; until then they
 * are declarative statements, which is the shape the AI Overviews on these
 * SERPs quote. The podcast row deliberately does not name a container format:
 * the builder emits WAV and no ffmpeg is bundled, so promising MP3 would break
 * the rule that every claim is true of the shipped app.
 */
const OUTPUTS: { heading: string; body: string; icon: ReactNode }[] = [
	{
		heading: "A deck",
		icon: <Presentation02Icon className="size-5" />,
		body: "An editable PPTX that opens in PowerPoint, Keynote and Google Slides. The version you send is one you edited, not one you rebuilt from a picture of a slide.",
	},
	{
		heading: "A report",
		icon: <File02Icon className="size-5" />,
		body: "An editable DOCX write-up with the structure you asked for, ready to revise and put on letterhead.",
	},
	{
		heading: "A briefing podcast",
		icon: <PodcastIcon className="size-5" />,
		body: "A two-voice conversation about the document, synthesised on your machine with a bundled speech model. No cloud text-to-speech and no per-minute fee for a twenty-minute internal explainer.",
	},
	{
		heading: "An infographic",
		icon: <ChartHistogramIcon className="size-5" />,
		body: "The figures that matter laid out as a single visual, for the slide where a table would lose the room.",
	},
	{
		heading: "A one-page summary",
		icon: <Pdf01Icon className="size-5" />,
		body: "The short version for the person who will not read the forty pages, written from all forty rather than from the first ten.",
	},
];

/** Short, checkable claims — the reference layout runs a claim beside a ruled
 *  list, and a list of adjectives would waste that structure. */
const WORKSPACE_PROOF: string[] = [
	"No account, no seat, no tenant",
	"Runs with the network unplugged",
	"Your own model, local or by key",
	"Files stay in the folder you chose",
	"Nothing held by a vendor to disclose",
	"Free, and the source is public",
];

function IconTile({ children }: { children: ReactNode }) {
	return (
		<span
			aria-hidden="true"
			className="grid size-11 place-items-center rounded-xl bg-secondary text-foreground"
		>
			{children}
		</span>
	);
}

/** The heads this page shares with the homepage: a centred badge over the title. */
function SectionHead({ badge, children }: { badge: string; children: ReactNode }) {
	return (
		<div className={cn("text-center", sectionSpacing.head)}>
			<HomeBadge>{badge}</HomeBadge>
			{children}
		</div>
	);
}

export default function PrivateAiForBusinessPage() {
	return (
		<>
			<section className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>Private AI for business</HomeBadge>
				<h1 className={cn(siteText.display, "mx-auto mt-4 max-w-4xl")}>
					Turn confidential documents into decks, reports and briefings,{" "}
					<span className="text-primary">offline</span>
				</h1>
				{/* The first paragraph is the whole argument, in the brief's order:
				    you have the file, the deliverable comes out here, nothing is
				    uploaded, so there is no copy for anyone to reach. */}
				<p className={cn(siteText.lede, "mx-auto mt-8 max-w-2xl")}>
					You already have the file. The deliverable comes out on the same machine it went in on:
					nothing is uploaded, so there is no vendor copy of your client's contract, your patient's
					notes or your firm's numbers, and nothing for anyone to subpoena from us.
				</p>
				<p className={cn(siteText.body, "mx-auto mt-5 max-w-2xl text-sm")}>
					A private AI workspace for lawyers, accountants, consultants and engineers. Free, with no
					account and no cloud behind it.
				</p>
				<div className="mt-10 flex justify-center">
					<HomeDownloadButton tone="dark" />
				</div>
			</section>

			<section className={sectionSpacing.foot}>
				{/* A `<p>` styled like an H2, so the three real H2s in this section are
				    the professions themselves rather than a fourth heading above them. */}
				<SectionHead badge="Who this is for">
					<p className={cn(siteText.h2, "mt-4")}>The job is the same in every profession</p>
				</SectionHead>

				<ul className="m-0 mt-10 grid list-none gap-4 p-0 md:grid-cols-3 lg:mt-14">
					{PROFESSIONS.map((profession) => (
						<li
							key={profession.heading}
							className="rounded-2xl border border-border bg-card p-6 shadow-xs md:p-8"
						>
							<IconTile>{profession.icon}</IconTile>
							<h2 className={cn(siteText.h3, "mt-6")}>{profession.heading}</h2>
							<p className={cn(siteText.body, "mt-2 text-sm")}>{profession.body}</p>
						</li>
					))}
				</ul>
			</section>

			<section className={sectionSpacing.foot}>
				<SectionHead badge="What comes out">
					<p className={cn(siteText.h2, "mt-4")}>One source set, five ways to hand it over</p>
				</SectionHead>

				{/* Six columns so five cards fill two rows evenly: three, then two wider. */}
				<ul className="m-0 mt-10 grid list-none gap-4 p-0 md:grid-cols-6 lg:mt-14">
					{OUTPUTS.map((output, index) => (
						<li
							key={output.heading}
							className={cn(
								"rounded-2xl border border-border bg-card p-6 shadow-xs md:p-8",
								index < 3 ? "md:col-span-2" : "md:col-span-3"
							)}
						>
							<IconTile>{output.icon}</IconTile>
							<h2 className={cn(siteText.h3, "mt-6")}>{output.heading}</h2>
							<p className={cn(siteText.body, "mt-2 text-sm")}>{output.body}</p>
						</li>
					))}
				</ul>

				<p className={cn(siteText.body, "mt-4 rounded-3xl bg-muted px-6 py-6 text-sm md:px-8")}>
					Every one of them also exports to PDF. What goes in is the file you already have: PDF,
					Word, PowerPoint, Excel, HTML, CSV, Markdown, plain text and images.
				</p>
			</section>

			<section className={sectionSpacing.foot}>
				<div className="flex flex-col overflow-hidden rounded-3xl bg-muted p-2 lg:flex-row">
					<div className="flex flex-col justify-center p-6 md:p-10 lg:w-1/2">
						<h2 className={siteText.h2}>One AI workspace, and it is a folder on your disk</h2>
						<div className={cn(siteText.body, "mt-5 flex flex-col gap-4")}>
							<p>
								Sources, chats and everything generated from them live in one local workspace: a
								directory in your user folder with a database file in it. Back it up, keep it on an
								encrypted volume, or delete the whole knowledge base by deleting the folder.
							</p>
							<p>
								There is no seat to provision, no tenant to configure and no admin console, because
								there is no server. The only identity involved is your operating system user.
							</p>
						</div>
						<p className="mt-6">
							<Link className={siteText.forward} href="/pricing">
								What a licence adds <ArrowRightIcon aria-hidden="true" className="size-4" />
							</Link>
						</p>
					</div>

					<ul className="m-0 flex list-none flex-col justify-center gap-4 rounded-2xl bg-card p-6 md:p-10 lg:w-1/2">
						{WORKSPACE_PROOF.map((point) => (
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

			{/* The compliance rule from `02-page-briefs.md` applies here verbatim:
			    state what is architecturally true and let the reader conclude. Nothing
			    on this page claims a regulation is satisfied. */}
			<section className={sectionSpacing.foot}>
				<div className="rounded-4xl border border-border bg-card px-6 py-10 shadow-xs md:px-12 md:py-14">
					<HomeBadge>Compliance</HomeBadge>
					<h2 className={cn(siteText.h2, "mt-4 max-w-3xl")}>
						Compliance depends on your controls, not on our software
					</h2>
					<div className={cn(siteText.body, "mt-6 flex max-w-3xl flex-col gap-4")}>
						<p>
							Whether a workflow is HIPAA, GDPR or SRA compliant depends on the controls around it,
							and those are yours to establish. No piece of software carries that property on its
							own.
						</p>
						<p>
							What we can tell you is narrower and checkable. The index and every prompt stay on
							your disk. We hold no copy, keep no log, and there is no account tying the two
							together. Custody never leaves you, so there is no vendor for anyone to serve. The
							source is public, so you can check all of that rather than take our word for it.
						</p>
					</div>
					<div className="mt-8">
						<HomeDownloadButton tone="dark" />
					</div>
				</div>
			</section>
		</>
	);
}
