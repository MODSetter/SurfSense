import { Check, Download } from "lucide-react";
import Link from "next/link";
import { HomeButton } from "@/components/homepage/home/home-button";
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
					<HomeButton asChild size="xl">
						<Link href={DOWNLOADS_URL}>
							<Download aria-hidden="true" />
							Download for desktop
						</Link>
					</HomeButton>
				</div>
			</div>
		</section>
	);
}

/**
 * A bento cell. `wide` spans both columns; `figure` adds the reference's
 * decorative grid bled in from the right edge.
 *
 * The first and last of four cells are wide, so the two-column grid fills
 * exactly — three single cells in two columns would leave one empty.
 */
function BentoCell({ title, body, wide, figure }: Cell & { wide?: boolean; figure?: boolean }) {
	return (
		<div className={`relative overflow-hidden ss-home-cell ${wide ? "ss-home-grid-wide" : ""}`}>
			{figure ? <div className="ss-home-figure" aria-hidden="true" /> : null}
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
 * The reference's `Features` split: the argument on the left, the evidence for
 * it as a bento grid on the right.
 */
export function HomeOnYourMachine() {
	const lastIndex = ON_YOUR_MACHINE.length - 1;

	return (
		<section className="ss-home-rule">
			<div className="ss-home-split">
				<div className="ss-home-statement">
					<h2 className="ss-home-h2">Runs entirely on your machine</h2>
					<p className="ss-home-body mt-6">
						Everything happens locally: parsing, embedding, search and generation. The index is a
						file on your disk, not a row in someone else&rsquo;s database, so the question of who
						else can read your sources does not arise.
					</p>
					<p className="ss-home-body mt-3">
						That is what air-gapped means here in the literal sense: the application keeps working
						with no network at all.
					</p>
				</div>

				<div className="ss-home-grid ss-home-grid-2">
					{ON_YOUR_MACHINE.map((cell, index) => (
						<BentoCell
							key={cell.title}
							{...cell}
							wide={index === 0 || index === lastIndex}
							figure={index === 0}
						/>
					))}
				</div>
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
 */
export function HomePillars() {
	return (
		<section className="ss-home-rule">
			<div className="ss-home-head">
				<p className="ss-home-eyebrow">Why it is different</p>
				<p className="ss-home-body mt-2 text-sm">
					Three things NotebookLM cannot do, because of how it is built rather than what it charges.
				</p>
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
									{pillar.action.label} <span aria-hidden="true">&rarr;</span>
								</a>
							) : (
								<Link className="ss-home-forward" href={pillar.action.href}>
									{pillar.action.label} <span aria-hidden="true">&rarr;</span>
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
 * stays intact. The caption names it for assistive technology instead.
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
				<p className="ss-home-body mt-2 text-sm">
					Compared on getting started, which is where a local notebook is either usable or not.
				</p>
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
 */
export function HomeFeatures() {
	return (
		<section className="ss-home-rule">
			<div className="ss-home-head">
				<p className="ss-home-eyebrow">What you get</p>
				<p className="ss-home-body mt-2 text-sm">
					Three claims, and the reasons each of them holds.
				</p>
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
											{story.action.label} <span aria-hidden="true">&rarr;</span>
										</a>
									) : (
										<Link className="ss-home-forward" href={story.action.href}>
											{story.action.label} <span aria-hidden="true">&rarr;</span>
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
