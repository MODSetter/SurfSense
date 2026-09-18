import type { Metadata } from "next";
import Link from "next/link";
import { DOWNLOADS_URL } from "@/components/site/site-content";
import { FlowButton } from "@/components/ui/flow-button";
import { CheckIcon } from "@/components/ui/icons";

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
 * A server component with no client JavaScript; every style resolves from
 * `app/(home)/home.css` and the chrome comes from `app/(home)/layout.tsx`.
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
		images: [
			{ url: "/og-image.png", width: 1200, height: 630, alt: "Private AI for business" },
		],
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
const PROFESSIONS: { heading: string; body: string }[] = [
	{
		heading: "For lawyers and legal teams",
		body: "Point it at a discovery folder and get an indexed evidence bundle, a chronology or a client letter back. Contract review runs against the executed copy sitting on your disk, and because nothing was sent to a vendor there is no third-party custodian holding it and no retention policy to read.",
	},
	{
		heading: "For accountants and auditors",
		body: "Add the statements, the ledger export and last year's working file, and get a reconciliation summary, a variance note or a board pack back. Client figures stay in the folder they arrived in and nowhere else.",
	},
	{
		heading: "For consultants and analysts",
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
const OUTPUTS: { heading: string; body: string }[] = [
	{
		heading: "A deck",
		body: "An editable PPTX that opens in PowerPoint, Keynote and Google Slides. The version you send is one you edited, not one you rebuilt from a picture of a slide.",
	},
	{
		heading: "A report",
		body: "An editable DOCX write-up with the structure you asked for, ready to revise and put on letterhead.",
	},
	{
		heading: "A briefing podcast",
		body: "A two-voice conversation about the document, synthesised on your machine with a bundled speech model. No cloud text-to-speech and no per-minute fee for a twenty-minute internal explainer.",
	},
	{
		heading: "An infographic",
		body: "The figures that matter laid out as a single visual, for the slide where a table would lose the room.",
	},
	{
		heading: "A one-page summary",
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

export default function PrivateAiForBusinessPage() {
	return (
		<>
			<section className="ss-home-hero ss-home-pad">
				<div className="mx-auto max-w-4xl text-center">
					<h1 className="ss-home-display">
						Turn confidential documents into decks, reports and briefings,{" "}
						<span className="ss-home-accent">offline</span>
					</h1>
					{/* The first paragraph is the whole argument, in the brief's order:
					    you have the file, the deliverable comes out here, nothing is
					    uploaded, so there is no copy for anyone to reach. */}
					<p className="ss-home-lede mx-auto mt-8 max-w-2xl">
						You already have the file. The deliverable comes out on the same machine it went in
						on: nothing is uploaded, so there is no vendor copy of your client's contract, your
						patient's notes or your firm's numbers, and nothing for anyone to subpoena from us.
					</p>
					<p className="ss-home-body mx-auto mt-5 max-w-2xl text-sm">
						A private AI workspace for lawyers, accountants, consultants and engineers. Free, with
						no account and no cloud behind it.
					</p>
					<div className="mt-10 flex justify-center">
						<FlowButton href={DOWNLOADS_URL} text="Download for desktop" />
					</div>
				</div>
			</section>

			<section className="ss-home-rule">
				<div className="ss-home-head">
					<p className="ss-home-eyebrow">Who this is for</p>
					{/* A `<p>` styled like an H2, so the three real H2s in this section
					    are the professions themselves rather than a fourth heading above
					    them — the same convention the landing page's bands use. */}
					<p className="ss-home-h2 mt-2">The job is the same in every profession</p>
				</div>

				<div className="ss-home-grid ss-home-grid-3">
					{PROFESSIONS.map((profession) => (
						<div key={profession.heading} className="ss-home-cell">
							<h2 className="ss-home-h3">{profession.heading}</h2>
							<p className="ss-home-body mt-2 text-sm">{profession.body}</p>
						</div>
					))}
				</div>
			</section>

			<section className="ss-home-rule">
				<div className="ss-home-head">
					<p className="ss-home-eyebrow">What comes out</p>
					<p className="ss-home-h2 mt-2">One source set, five ways to hand it over</p>
				</div>

				<div className="ss-home-grid ss-home-grid-3">
					{OUTPUTS.map((output, index) => (
						<div
							key={output.heading}
							// The fifth cell spans the empty column so the last row of a
							// three-column grid does not leave a gap showing the grid's
							// own border colour.
							className={
								index === OUTPUTS.length - 1 ? "ss-home-cell ss-home-grid-span-2" : "ss-home-cell"
							}
						>
							<h2 className="ss-home-h3">{output.heading}</h2>
							<p className="ss-home-body mt-2 text-sm">{output.body}</p>
						</div>
					))}
				</div>

				<div className="ss-home-rule ss-home-pad py-8">
					<p className="ss-home-body max-w-4xl text-sm">
						Every one of them also exports to PDF. What goes in is the file you already have:
						PDF, Word, PowerPoint, Excel, HTML, CSV, Markdown, plain text and images.
					</p>
				</div>
			</section>

			<section className="ss-home-rule ss-home-split">
				<div className="ss-home-statement">
					<h2 className="ss-home-h2">One AI workspace, and it is a folder on your disk</h2>
					<div className="ss-home-body mt-5 flex flex-col gap-4">
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
						<Link className="ss-home-forward" href="/pricing">
							What a licence adds
						</Link>
					</p>
				</div>

				<ul className="ss-home-grid m-0 list-none p-0">
					{WORKSPACE_PROOF.map((point) => (
						<li key={point} className="flex items-center gap-3 px-(--home-gutter) py-3.5">
							<CheckIcon aria-hidden="true" className="size-3.5 shrink-0 text-(--home-accent)" />
							<span className="ss-home-body text-sm">{point}</span>
						</li>
					))}
				</ul>
			</section>

			{/* The compliance rule from `02-page-briefs.md` applies here verbatim:
			    state what is architecturally true and let the reader conclude. Nothing
			    on this page claims a regulation is satisfied. */}
			<section className="ss-home-rule">
				<div className="ss-home-head ss-home-head-plain">
					<p className="ss-home-eyebrow">Compliance</p>
					<h2 className="ss-home-h2 mt-2">Compliance depends on your controls, not on our software</h2>
				</div>

				<div className="ss-home-pad pb-12">
					<div className="ss-home-body flex max-w-3xl flex-col gap-4">
						<p>
							Whether a workflow is HIPAA, GDPR or SRA compliant depends on the controls around
							it, and those are yours to establish. No piece of software carries that property on
							its own.
						</p>
						<p>
							What we can tell you is narrower and checkable. The index and every prompt stay on
							your disk. We hold no copy, keep no log, and there is no account tying the two
							together. Custody never leaves you, so there is no vendor for anyone to serve. The
							source is public, so you can check all of that rather than take our word for it.
						</p>
					</div>

					<p className="mt-8">
						<Link className="ss-home-forward" href={DOWNLOADS_URL}>
							Download for Windows, macOS or Linux
						</Link>
					</p>
				</div>
			</section>
		</>
	);
}
