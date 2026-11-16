// Column heights in %, the last one called out as the latest figure.
const COLUMNS = [35, 50, 42, 64, 58, 78, 92].map((height, id) => ({ height, id }));
const LATEST = COLUMNS.length - 1;

/** A one-page visual: a headline ratio, a supporting stat, a trend. */
export function InfographicPreview() {
	return (
		<div className="flex w-full max-w-48 flex-col gap-3 rounded-xl bg-card p-4 shadow-sm ring-1 ring-black/5">
			<span className="h-1.5 w-20 rounded-full bg-foreground/60" />

			<div className="flex items-center gap-3">
				<div className="relative size-14 shrink-0">
					{/* r = 100 / 2π, so the dash reads directly as a percentage. */}
					<svg aria-hidden="true" viewBox="0 0 36 36" className="size-full -rotate-90">
						<circle
							cx="18"
							cy="18"
							r="15.9155"
							className="fill-none stroke-muted-foreground/15"
							strokeWidth={4}
						/>
						<circle
							cx="18"
							cy="18"
							r="15.9155"
							className="fill-none stroke-(--notice)"
							strokeWidth={4}
							strokeDasharray="84 16"
							strokeLinecap="round"
						/>
					</svg>
					<span className="absolute inset-0 grid place-items-center text-xs font-semibold text-foreground tabular-nums">
						84%
					</span>
				</div>
				<div className="flex min-w-0 flex-col gap-1">
					<span className="text-base leading-none font-semibold tracking-tight text-foreground tabular-nums">
						3.2×
					</span>
					<span className="h-1.5 w-14 rounded-full bg-muted-foreground/25" />
					<span className="h-1.5 w-10 rounded-full bg-muted-foreground/25" />
				</div>
			</div>

			<div className="flex h-10 items-end gap-1 border-b border-border">
				{COLUMNS.map((column) => (
					<span
						key={column.id}
						className={
							column.id === LATEST
								? "flex-1 rounded-t-sm bg-(--notice)"
								: "flex-1 rounded-t-sm bg-(--home-sky)"
						}
						style={{ height: `${column.height}%` }}
					/>
				))}
			</div>
		</div>
	);
}
