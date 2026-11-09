// Bar heights in px, drawn once; the first stretch reads as already played.
const BARS = [
	6, 14, 22, 10, 28, 18, 8, 24, 32, 16, 12, 26, 20, 9, 30, 22, 14, 6, 18, 27, 12, 20, 8, 16,
].map((height, id) => ({ height, id }));
const PLAYED = 10;

/** A two-voice episode mid-play: both hosts, a waveform, the scrub times. */
export function PodcastPreview() {
	return (
		<div className="w-full max-w-sm rounded-xl bg-card p-5 shadow-sm ring-1 ring-black/5">
			<div className="flex items-center gap-3">
				<div className="flex -space-x-2">
					<span className="size-8 rounded-full bg-(--home-sky) ring-2 ring-card" />
					<span className="size-8 rounded-full bg-(--notice) ring-2 ring-card" />
				</div>
				<div className="flex flex-col gap-1.5">
					<span className="h-2 w-28 rounded-full bg-foreground/70" />
					<span className="h-1.5 w-20 rounded-full bg-muted-foreground/30" />
				</div>
			</div>
			<div className="mt-6 flex h-9 items-center gap-[3px]">
				{BARS.map((bar) => (
					<span
						key={bar.id}
						className={
							bar.id < PLAYED
								? "flex-1 rounded-full bg-(--notice)"
								: "flex-1 rounded-full bg-muted-foreground/25"
						}
						style={{ height: bar.height }}
					/>
				))}
			</div>
			<div className="mt-4 flex items-center justify-between text-[11px] text-muted-foreground tabular-nums">
				<span>4:12</span>
				<span className="grid size-8 place-items-center rounded-full bg-foreground text-background">
					<svg aria-hidden="true" viewBox="0 0 12 12" className="ml-0.5 size-3 fill-current">
						<path d="M2 1.5v9l8-4.5z" />
					</svg>
				</span>
				<span>12:40</span>
			</div>
		</div>
	);
}
