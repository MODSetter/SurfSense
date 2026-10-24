import { AirGapDiagram } from "@/components/homepage/home/home-air-gap/air-gap-diagram";
import { AirGapScrollSteps } from "@/components/homepage/home/home-air-gap/air-gap-scroll-steps";
import { HomeAnnouncement } from "@/components/homepage/home/home-announcement";
import { HomeBadge } from "@/components/homepage/home/home-badge";
import { HomeDownloadButton } from "@/components/homepage/home/home-download-button";
import { HomeScene } from "@/components/homepage/home/home-scene";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/lib/utils";

/**
 * Homepage sections.
 *
 * The layout vocabulary is ported from `homepage-reference/`: every section is
 * a ruled band inside one bordered column, splits are two halves separated by a
 * hairline, and cell grids are drawn with a 1px gap over the border colour so
 * no interior rule ever doubles up. Nothing here has a radius or a shadow; only
 * controls keep the palette's `--radius`. `HomeFormats` (its own folder) is the
 * exception: rounded cards with miniatures, in the painted scenes' language.
 * Styled with Tailwind plus the shared `siteText` styles.
 *
 * Server components only; sections with client parts live in their own folders.
 *
 * The heading order is not editorial. It is the SEO skeleton from
 * `plans/community-local/seo/02-page-briefs.md`: H1, then eight H2s in a fixed
 * order. Sections may be restyled freely; the sequence of headings may not be
 * reordered without re-reading that brief.
 */

export function HomeHero() {
	return (
		// Full bleed, and pulled up under the sticky nav (`-mt-20` is the nav's
		// height) so the scene starts at the top edge of the page. Copy sits in
		// the sky, where the wash keeps white text readable.
		<section className="-mt-20" data-bleed>
			<div className="relative flex min-h-[calc(100svh+4rem)] flex-col items-center justify-center overflow-hidden px-6 pt-32 pb-40 text-center md:px-10 lg:pb-96">
				{/* 1.73 times the hero's height, the cover width on portrait screens. */}
				<HomeScene priority sizes="max(100vw, calc(173vh + 7rem))" />
				<div
					aria-hidden="true"
					className="absolute inset-0 bg-linear-to-b from-black/45 via-black/20 to-transparent"
				/>
				{/* Dissolves the scene into the page. It sits in the 4rem the hero runs
				    past the fold (pb-40 offsets it so the copy stays centred), so the
				    first screen shows no fade. On desktop lg:pb-96 lifts the copy clear
				    of the dome. */}
				<div
					aria-hidden="true"
					className="absolute inset-x-0 bottom-0 h-16 bg-linear-to-b from-transparent to-background"
				/>

				<div className="relative mx-auto max-w-4xl">
					<HomeAnnouncement />
					<h1 className={cn(siteText.display, "text-white")}>
						Air-gapped, open source NotebookLM alternative
					</h1>
					<p className="mx-auto mt-8 max-w-2xl text-base leading-relaxed text-pretty text-white/85 md:text-lg lg:text-xl">
						A private research notebook that runs entirely on your own machine. Your documents, your
						model keys, no cloud, no account.
					</p>
					<div className="mt-10 flex justify-center">
						<HomeDownloadButton />
					</div>
				</div>
			</div>
		</section>
	);
}

/**
 * H2 #1 — the offline / local / air-gapped claim.
 *
 * Drawn as one system diagram, not a row of cells: `HomePillars` directly
 * below is already a three-column row, and the diagram shows the air gap
 * rather than asserting it.
 *
 * The headline is the brief's exact H2 #1 text; `How it works` is the pill above
 * it instead of replacing it.
 */
export function HomeOnYourMachine() {
	return (
		<section>
			{/* On lg the whole frame pins for one screen (pt-20 clears the nav) and
			    only the diagram changes as you scroll; below lg it flows normally. */}
			<AirGapScrollSteps className="pt-10 pb-16 md:pt-24 lg:sticky lg:top-0 lg:flex lg:h-svh lg:flex-col lg:justify-center lg:pt-20 lg:pb-0">
				<div className="text-center">
					<HomeBadge>How it works</HomeBadge>
					<h2 className={cn(siteText.h2, "mt-4")}>Runs entirely on your machine</h2>
				</div>
				<AirGapDiagram className="mt-10 lg:mt-14" />
			</AirGapScrollSteps>
		</section>
	);
}
