import { PlusIcon } from "lucide-react";
import { COMPANIES } from "@/components/homepage/home/home-content";
import { cn } from "@/lib/utils";

/**
 * "Trusted by experts at" — a logo cloud.
 *
 * The 4 x 2 stack, its checkerboard of `secondary` cells and the plus marks at
 * the interior corners are taken from the `logo-cloud-2` component. That grid
 * is fixed at eight cells, and there are twenty names to show, so each cell
 * holds its share stacked on top of each other and cross-fades between them.
 *
 * The cross-fade is pure CSS: keyframes on stacked `img`s, no timer, no state,
 * no client JavaScript. That matters here because it means every one of the
 * twenty logos — and its `alt` text — is in the server-rendered HTML at once,
 * so a crawler and a screen reader get the whole list regardless of which
 * frame is painted. A `setInterval` swapping ten of them would not.
 *
 * Marks keep their own drawing, desaturated for cohesion, and are inverted so
 * dark artwork stays visible on the dark ground. Logos that are already light
 * opt out (see `home-content`).
 */

/** Eight cells, twenty logos, dealt round-robin: cell `i` gets logos `i`,
 *  `i + 8` and `i + 16`. Four cells end up with three and four with two, which
 *  is what makes the cells drift out of step with each other instead of
 *  flipping in unison. */
const CELL_COUNT = 8;

const CELLS = Array.from({ length: CELL_COUNT }, (_, cell) =>
	COMPANIES.filter((_company, index) => index % CELL_COUNT === cell)
);

/** Card classes, cell by cell, from `logo-cloud-2`. The checkerboard differs
 *  between the two-column and four-column layouts because the cells land in
 *  different places, so several of these swap their tint at `md`. */
const CARD_CLASSES = [
	"border-r border-b bg-secondary",
	"border-b md:border-r",
	"border-r border-b md:bg-secondary",
	"border-b bg-secondary md:bg-background",
	"border-r border-b md:border-b-0 bg-secondary md:bg-background",
	"border-b md:border-r md:border-b-0 bg-background md:bg-secondary",
	"border-r",
	"bg-secondary",
];

const PLUS_CLASS = "ss-home-logo-plus absolute z-10 size-6";

/** The registration marks that sit where four cells meet. */
function CellMarks({ cell }: { cell: number }) {
	if (cell === 0) {
		return (
			<PlusIcon
				aria-hidden="true"
				className={cn(PLUS_CLASS, "-right-[12.5px] -bottom-[12.5px]")}
				strokeWidth={1}
			/>
		);
	}
	if (cell === 2) {
		return (
			<>
				<PlusIcon
					aria-hidden="true"
					className={cn(PLUS_CLASS, "-right-[12.5px] -bottom-[12.5px]")}
					strokeWidth={1}
				/>
				<PlusIcon
					aria-hidden="true"
					className={cn(PLUS_CLASS, "-bottom-[12.5px] -left-[12.5px] hidden md:block")}
					strokeWidth={1}
				/>
			</>
		);
	}
	if (cell === 4) {
		return (
			<PlusIcon
				aria-hidden="true"
				className={cn(PLUS_CLASS, "-right-[12.5px] -bottom-[12.5px] md:-left-[12.5px] md:hidden")}
				strokeWidth={1}
			/>
		);
	}
	return null;
}

export function HomeLogos() {
	// Labelled with a paragraph rather than a heading on purpose: the brief fixes
	// the H1 and the seven H2s that follow it, and an eighth heading here would
	// sit in the middle of that sequence.
	return (
		<section className="ss-home-rule" aria-labelledby="ss-home-logos-label">
			<div className="ss-home-pad pt-12 pb-8">
				<p id="ss-home-logos-label" className="ss-home-section-label">
					Trusted by <span className="ss-home-section-label-accent">experts</span> at
				</p>
			</div>

			{/* The label no longer sits in a ruled header, so the grid draws its own
			    top edge — otherwise the first row would open against nothing. */}
			<div className="relative grid grid-cols-2 border-t border-[color:var(--border)] md:grid-cols-4">
				{CELLS.map((companies, cell) => (
					<div
						key={CARD_CLASSES[cell]}
						className={cn(
							"ss-home-logo-card relative flex items-center justify-center border-[color:var(--border)] bg-background px-4 py-8 md:p-8",
							CARD_CLASSES[cell]
						)}
					>
						{companies.map((company, slot) => (
							// biome-ignore lint/performance/noImgElement: fixed-size local logo marks; next/image adds a loader and layout machinery for no benefit here
							<img
								key={company.title}
								src={`/logos/${company.file}`}
								alt={company.title}
								title={company.title}
								width={130}
								height={40}
								loading="lazy"
								decoding="async"
								className="ss-home-logo"
								data-light={company.light === true ? "" : undefined}
								data-first={slot === 0 ? "" : undefined}
								data-slots={companies.length}
								style={{ "--slot": slot } as React.CSSProperties}
							/>
						))}

						<CellMarks cell={cell} />
					</div>
				))}
			</div>
		</section>
	);
}
