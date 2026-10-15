/** A small deck: the next card tilted behind the question on top. */
export function FlashcardsPreview() {
	return (
		<div className="relative h-28 w-40">
			<div className="absolute inset-0 rotate-6 rounded-xl bg-card/70 ring-1 ring-black/5" />
			<div className="absolute inset-0 -rotate-3 flex flex-col justify-center gap-2 rounded-xl bg-card p-4 shadow-sm ring-1 ring-black/5">
				<span className="text-xs font-semibold text-(--notice)">Q</span>
				<span className="h-1.5 w-full rounded-full bg-foreground/60" />
				<span className="h-1.5 w-2/3 rounded-full bg-foreground/60" />
			</div>
		</div>
	);
}
