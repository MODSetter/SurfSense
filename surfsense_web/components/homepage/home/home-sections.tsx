import Link from "next/link";
import { HomeArtifactIllustration } from "@/components/homepage/home/home-artifact-illustration";
import {
	type Cell,
	COMPARE_ROWS,
	CONFIDENTIAL,
	DOWNLOADS_URL,
	FORMATS,
	type IllustratedCell,
	ON_YOUR_MACHINE,
	PILLARS,
} from "@/components/homepage/home/home-content";
import { HomeFeaturesTabs } from "@/components/homepage/home/home-features-tabs";
import { HomeFormatCell } from "@/components/homepage/home/home-format-cell";
import { HomeHeroDither } from "@/components/homepage/home/home-hero-dither";
import { FlowButton } from "@/components/ui/flow-button";
import { ArrowRightIcon } from "@/components/ui/icons";

/**
 * Homepage sections.
 *
 * The layout vocabulary is ported from `homepage-reference/`: every section is
 * a ruled band inside one bordered column, splits are two halves separated by a
 * hairline, and cell grids are drawn with a 1px gap over the border colour so
 * no interior rule ever doubles up. Nothing here has a radius or a shadow; only
 * controls keep the palette's `--radius`.
 *
 * Mostly server components. Three exceptions live in their own "use client"
 * modules rather than pulling this file across the boundary: the hero's
 * backdrop (a WebGL shader), `HomeFeaturesTabs` (the claims switcher), and
 * `CardSpotlight` (components/ui), which `HomeFormatCell` wraps each format
 * cell in for its hover spotlight.
 *
 * The heading order is not editorial. It is the SEO skeleton from
 * `plans/community-local/seo/02-page-briefs.md`: H1, then eight H2s in a fixed
 * order. Sections may be restyled freely; the sequence of headings may not be
 * reordered without re-reading that brief.
 */

export function HomeHero() {
	return (
		<section className="ss-home-hero ss-home-pad">
			<HomeHeroDither />
			<div className="relative mx-auto max-w-4xl text-center">
				<h1 className="ss-home-display">
					Air-gapped, open source <span className="ss-home-accent">NotebookLM alternative</span>
				</h1>
				<p className="ss-home-lede mx-auto mt-8 max-w-2xl">
					A private research notebook that runs entirely on your own machine. Your documents, your
					model keys, no cloud, no account.
				</p>
				<div className="mt-10 flex justify-center">
					<FlowButton href={DOWNLOADS_URL} text="Download for desktop" />
				</div>
			</div>
		</section>
	);
}

/**
 * A bento cell. `illustration` renders a designed SVG in place of the usual
 * figure — some cells in this grid have something to show rather than only
 * say.
 */
function BentoCell({ title, body, illustration }: Cell & { illustration?: IllustratedCell }) {
	return (
		<div className="relative overflow-hidden ss-home-cell">
			{illustration ? <HomeArtifactIllustration illustration={illustration} /> : null}
			<div className="relative">
				<p className="ss-home-h3">{title}</p>
				<p className="ss-home-body mt-1.5 max-w-sm text-sm">{body}</p>
			</div>
		</div>
	);
}

/**
 * H2 #1 — the offline / local / air-gapped claim.
 *
 * A plain heading band, not a fourth cell: the eyebrow-plus-headline pair
 * introduces the row of three bento cells below it rather than sitting beside
 * them as an equal-weight panel, the way `HomePillars` introduces its own row.
 *
 * The headline is the brief's exact H2 #1 text; `Features` moved up to become
 * the small kicker above it instead of replacing it.
 */
export function HomeOnYourMachine() {
	return (
		<section className="ss-home-rule">
			<div className="ss-home-head ss-home-head-plain">
				<p className="ss-home-eyebrow">Features</p>
				<h2 className="ss-home-h2 mt-2">Runs entirely on your machine</h2>
			</div>

			<div className="ss-home-grid ss-home-grid-3 ss-home-grid-dashed">
				{ON_YOUR_MACHINE.map((cell) => (
					<BentoCell key={cell.title} {...cell} />
				))}
			</div>
		</section>
	);
}

/**
 * H2 #2, #3, #4 — one ruled row, three arguments.
 *
 * The reference's `Services` cards: a headline, a short body, and a forward
 * link pinned to the bottom of the cell so the three links line up regardless
 * of how long each body runs.
 *
 * The band's own headline is a `<p>` styled like an H2, not a real one — the
 * three real H2s the brief wants are the pillar titles below it, and adding a
 * fourth here would leave the section carrying two.
 */
export function HomePillars() {
	return (
		<section className="ss-home-rule">
			<div className="ss-home-head ss-home-head-plain">
				<p className="ss-home-eyebrow">Why it is different</p>
				<p className="ss-home-h2 mt-2">Three things NotebookLM cannot do</p>
			</div>

			<div className="ss-home-grid ss-home-grid-3 ss-home-grid-dashed">
				{PILLARS.map((pillar) => (
					<div key={pillar.title} className="ss-home-cell flex flex-col">
						<h2 className="ss-home-h3">{pillar.title}</h2>
						<p className="ss-home-body mt-2 text-sm">{pillar.body}</p>
						<p className="mt-auto pt-6">
							{pillar.action.external ? (
								<a
									className="ss-home-forward"
									href={pillar.action.href}
									target="_blank"
									rel="noreferrer noopener"
								>
									{pillar.action.label} <ArrowRightIcon aria-hidden="true" className="size-4" />
								</a>
							) : (
								<Link className="ss-home-forward" href={pillar.action.href}>
									{pillar.action.label} <ArrowRightIcon aria-hidden="true" className="size-4" />
								</Link>
							)}
						</p>
					</div>
				))}
			</div>
		</section>
	);
}

/**
 * The comparison table carries no heading of its own, so the brief's H2 order
 * stays intact — the headline below is a `<p>` styled like an H2, not a real
 * one. The caption names the table for assistive technology instead.
 *
 * The scroller is focusable and labelled: on a narrow screen the table is wider
 * than the column, and a keyboard visitor needs to be able to scroll it without
 * a pointer.
 */
export function HomeCompare() {
	return (
		<section className="ss-home-rule">
			<div className="ss-home-head">
				<p className="ss-home-eyebrow">How it compares</p>
				<p className="ss-home-h2 mt-2">Getting started, compared</p>
			</div>

			<section
				className="ss-home-table-scroll"
				aria-label="Scrollable comparison table"
				/* biome-ignore lint/a11y/noNoninteractiveTabindex: a region that scrolls horizontally has to be focusable, or a keyboard-only visitor cannot reach the columns past the fold. The labelled landmark is what makes the focus stop meaningful. */
				tabIndex={0}
			>
				<table className="ss-home-table">
					<caption className="sr-only">
						SurfSense compared with NotebookLM, AnythingLLM and Open Notebook
					</caption>
					<thead>
						<tr>
							<th scope="col">
								<span className="sr-only">Capability</span>
							</th>
							<th scope="col" data-col="ours">
								SurfSense
							</th>
							<th scope="col">NotebookLM</th>
							<th scope="col">AnythingLLM</th>
							<th scope="col">Open Notebook</th>
						</tr>
					</thead>
					<tbody>
						{COMPARE_ROWS.map((row) => (
							<tr key={row.label}>
								<th scope="row">{row.label}</th>
								<td data-col="ours">{row.ours}</td>
								<td>{row.notebooklm}</td>
								<td>{row.anythingllm}</td>
								<td>{row.openNotebook}</td>
							</tr>
						))}
					</tbody>
				</table>
			</section>
		</section>
	);
}

/**
 * H2 #5, #6, #7 — the reference's `Pricing` block: a header, then cells that
 * pair a claim with the concrete things that back it, each ruled off from the
 * next.
 *
 * The band's own headline is a `<p>` styled like an H2, not a real one — the
 * three real H2s the brief wants are each story's own heading, rendered by
 * `HomeFeaturesTabs` below.
 */
export function HomeFeatures() {
	return (
		<section className="ss-home-rule">
			<div className="ss-home-head">
				<p className="ss-home-eyebrow">What you get</p>
				<p className="ss-home-h2 mt-2">Three things worth knowing before you install</p>
			</div>

			<HomeFeaturesTabs />
		</section>
	);
}

/**
 * H2 #8 — *For confidential work*, added to the brief on 17 Sep 2026.
 *
 * Sits directly after H2 #7 (*Private by construction*, the last of the claims
 * tabs) because it answers the question that one raises: privacy for whom. The
 * brief asks for one paragraph rather than a section, so this is a single
 * statement band with no grid and no proof list — the argument is made in full
 * on the page it links to.
 */
export function HomeConfidential() {
	return (
		<section className="ss-home-rule">
			<div className="ss-home-pad py-16 md:py-24">
				<div className="max-w-3xl">
					<p className="ss-home-eyebrow">{CONFIDENTIAL.eyebrow}</p>
					<h2 className="ss-home-h2 mt-2">{CONFIDENTIAL.heading}</h2>
					<p className="ss-home-body mt-5">{CONFIDENTIAL.body}</p>
					<p className="mt-6">
						<Link className="ss-home-forward" href={CONFIDENTIAL.action.href}>
							{CONFIDENTIAL.action.label}{" "}
							<ArrowRightIcon aria-hidden="true" className="size-4" />
						</Link>
					</p>
				</div>
			</div>
		</section>
	);
}

/**
 * Not one of the brief's eight H2s (see `FORMATS`'s own doc comment in
 * `home-content.ts`) — a bento row of the twelve Studio formats, below the
 * claims tabs. `HomeFormatCell` is the one client component in the row (a
 * cursor-tracked hover spotlight); this section itself stays server-rendered.
 */
export function HomeFormats() {
	return (
		<section className="ss-home-rule">
			<div className="ss-home-head ss-home-head-plain">
				<p className="ss-home-eyebrow">Artifacts</p>
				<p className="ss-home-h2 mt-2">Twelve things one set of sources can become</p>
			</div>

			{/* The same grid as the logo cloud: the head is plain, so the grid draws its
			    own top edge, and each cell draws its own right and bottom hairlines. */}
			<div className="relative grid grid-cols-2 border-t border-[color:var(--border)] md:grid-cols-4">
				{FORMATS.map((format, index) => (
					<HomeFormatCell key={format.key} format={format} index={index} />
				))}
			</div>
		</section>
	);
}
