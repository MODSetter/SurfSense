import { ArrowRight, Check } from "lucide-react";
import Link from "next/link";
import { HomeArtifactIllustration } from "@/components/homepage/home/home-artifact-illustration";
import {
	type Cell,
	COMPARE_ROWS,
	DOWNLOADS_URL,
	ON_YOUR_MACHINE,
	PILLARS,
	PROOF_POINTS,
	STORIES,
} from "@/components/homepage/home/home-content";
import { HomeHeroDither } from "@/components/homepage/home/home-hero-dither";
import { FlowButton } from "@/components/ui/flow-button";

/**
 * Homepage sections.
 *
 * The layout vocabulary is ported from `homepage-reference/`: every section is
 * a ruled band inside one bordered column, splits are two halves separated by a
 * hairline, and cell grids are drawn with a 1px gap over the border colour so
 * no interior rule ever doubles up. Nothing here has a radius or a shadow; only
 * controls keep the palette's `--radius`.
 *
 * All server components — the page has no interactive state. The single
 * exception is the hero's backdrop, which is a WebGL shader and so lives in its
 * own "use client" module rather than pulling this file across the boundary.
 *
 * The heading order is not editorial. It is the SEO skeleton from
 * `plans/community-local/seo/02-page-briefs.md`: H1, then seven H2s in a fixed
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
 * A bento cell. `illustration` renders the artifact flow diagram in place of
 * the usual figure — the one cell in this grid with something to show rather
 * than only say.
 */
function BentoCell({ title, body, illustration }: Cell & { illustration?: boolean }) {
	return (
		<div className="relative overflow-hidden ss-home-cell">
			{illustration ? <HomeArtifactIllustration /> : null}
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
	const lastIndex = ON_YOUR_MACHINE.length - 1;

	return (
		<section className="ss-home-rule">
			<div className="ss-home-head ss-home-head-plain">
				<p className="ss-home-eyebrow">Features</p>
				<h2 className="ss-home-h2 mt-2">Runs entirely on your machine</h2>
			</div>

			<div className="ss-home-grid ss-home-grid-3 ss-home-grid-dashed">
				{ON_YOUR_MACHINE.map((cell, index) => (
					<BentoCell key={cell.title} {...cell} illustration={index === lastIndex} />
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
		<section className="ss-home-rule ss-home-rule-plain">
			<div className="ss-home-head">
				<p className="ss-home-eyebrow">Why it is different</p>
				<p className="ss-home-h2 mt-2">Three things NotebookLM cannot do</p>
			</div>

			<div className="ss-home-grid ss-home-grid-3">
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
									{pillar.action.label} <ArrowRight aria-hidden="true" className="size-4" />
								</a>
							) : (
								<Link className="ss-home-forward" href={pillar.action.href}>
									{pillar.action.label} <ArrowRight aria-hidden="true" className="size-4" />
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
 * three real H2s the brief wants are each story's own heading below it.
 */
export function HomeFeatures() {
	return (
		<section className="ss-home-rule">
			<div className="ss-home-head">
				<p className="ss-home-eyebrow">What you get</p>
				<p className="ss-home-h2 mt-2">Three claims, and why each one holds</p>
			</div>

			<div className="ss-home-grid">
				{STORIES.map((story) => (
					<div key={story.heading} className="flex flex-col">
						<div className="ss-home-split">
							<div className="ss-home-statement">
								<h2 className="ss-home-h2">{story.heading}</h2>
								<div className="ss-home-body mt-5 flex flex-col gap-4">
									{story.body.map((paragraph) => (
										<p key={paragraph}>{paragraph}</p>
									))}
								</div>
								<p className="mt-6">
									{story.action.external ? (
										<a
											className="ss-home-forward"
											href={story.action.href}
											target="_blank"
											rel="noreferrer noopener"
										>
											{story.action.label} <ArrowRight aria-hidden="true" className="size-4" />
										</a>
									) : (
										<Link className="ss-home-forward" href={story.action.href}>
											{story.action.label} <ArrowRight aria-hidden="true" className="size-4" />
										</Link>
									)}
								</p>
							</div>

							<ul className="ss-home-grid m-0 list-none p-0">
								{PROOF_POINTS[story.key].map((point) => (
									<li key={point} className="flex items-center gap-3 px-(--home-gutter) py-3.5">
										<Check aria-hidden="true" className="size-3.5 shrink-0 text-(--home-accent)" />
										<span className="ss-home-body text-sm">{point}</span>
									</li>
								))}
							</ul>
						</div>
					</div>
				))}
			</div>
		</section>
	);
}
