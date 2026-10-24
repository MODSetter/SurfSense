import { cn } from "@/lib/utils";

// The deck's other slides, each a different layout so it reads as a real deck.
const THUMBNAILS = ["title", "chart", "bullets", "quote"] as const;
const BULLETS = ["w-full", "w-5/6", "w-2/3"];
const CHART = ["h-[45%]", "h-[70%]", "h-[55%]", "h-full"];

function Thumbnail({ layout, active }: { layout: (typeof THUMBNAILS)[number]; active: boolean }) {
	return (
		<div
			className={cn(
				"flex aspect-video flex-col gap-0.5 overflow-hidden rounded-sm bg-card p-1 ring-1 ring-black/10",
				active && "ring-2 ring-(--notice)"
			)}
		>
			{layout === "title" && (
				<>
					<span className="mt-auto h-1 w-3/4 rounded-full bg-foreground/60" />
					<span className="mb-auto h-0.5 w-1/2 rounded-full bg-muted-foreground/30" />
				</>
			)}
			{layout === "chart" && (
				<div className="flex flex-1 items-end gap-0.5">
					{CHART.map((height) => (
						<span key={height} className={cn("flex-1 rounded-[1px] bg-(--notice)/60", height)} />
					))}
				</div>
			)}
			{layout === "bullets" && (
				<div className="flex flex-1 flex-col justify-center gap-1 pl-0.5">
					{BULLETS.map((width) => (
						<div key={width} className="flex items-center gap-1">
							<span className="size-1 shrink-0 rounded-full bg-(--notice)" />
							<span className={cn("h-0.5 rounded-full bg-muted-foreground/40", width)} />
						</div>
					))}
				</div>
			)}
			{layout === "quote" && (
				<div className="flex flex-1 flex-col items-center justify-center gap-0.5 bg-(--home-sky-soft)">
					<span className="font-serif text-xs leading-none text-(--notice)">&ldquo;</span>
					<span className="h-0.5 w-2/3 rounded-full bg-foreground/50" />
					<span className="h-0.5 w-1/2 rounded-full bg-foreground/50" />
				</div>
			)}
		</div>
	);
}

/** The deck open in an editor: the current slide large, the rest in a strip. */
export function SlidesPreview() {
	return (
		<div className="flex w-full max-w-sm flex-col gap-2.5">
			<div className="grid aspect-video grid-cols-[1.1fr_1fr] gap-4 rounded-lg bg-card p-4 shadow-sm ring-1 ring-black/5">
				<div className="flex flex-col justify-center gap-1.5">
					<span className="h-1.5 w-10 rounded-full bg-(--notice)/60" />
					<span className="mt-1 h-2.5 w-full rounded-full bg-foreground/80" />
					<span className="h-2.5 w-2/3 rounded-full bg-foreground/80" />
					<span className="mt-2 h-1.5 w-full rounded-full bg-muted-foreground/25" />
					<span className="h-1.5 w-4/5 rounded-full bg-muted-foreground/25" />
				</div>
				{/* A rising trend: a line over its filled area. */}
				<svg
					aria-hidden="true"
					viewBox="0 0 100 80"
					preserveAspectRatio="none"
					className="size-full rounded-md bg-(--home-sky-soft)"
				>
					<path
						d="M8 64 L28 52 L46 56 L64 34 L84 22 L84 72 L8 72 Z"
						className="fill-(--notice)/15"
					/>
					<path
						d="M8 64 L28 52 L46 56 L64 34 L84 22"
						className="fill-none stroke-(--notice)"
						strokeWidth={2.5}
						strokeLinecap="round"
						strokeLinejoin="round"
						vectorEffect="non-scaling-stroke"
					/>
					<path d="M8 72 H84" className="stroke-black/10" vectorEffect="non-scaling-stroke" />
				</svg>
			</div>
			<div className="grid grid-cols-4 gap-2">
				{THUMBNAILS.map((layout, index) => (
					<Thumbnail key={layout} layout={layout} active={index === 0} />
				))}
			</div>
		</div>
	);
}
