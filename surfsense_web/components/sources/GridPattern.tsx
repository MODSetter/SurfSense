export function GridPattern() {
	const columns = 41;
	const rows = 11;
	return (
		<div className="flex bg-transparent flex-shrink-0 flex-wrap justify-center items-center gap-x-px gap-y-px scale-105">
			{Array.from({ length: rows }).map((_, row) =>
				Array.from({ length: columns }).map((_, col) => {
					const index = row * columns + col;
					return (
						<div
							key={`${col}-${row}`}
							className={`w-10 h-10 flex flex-shrink-0 rounded-[2px] ${
								index % 2 === 0
									? "bg-slate-200/20 dark:bg-slate-400/10"
									: "bg-slate-300/30 dark:bg-slate-500/15 shadow-[0px_0px_1px_3px_rgba(255,255,255,0.1)_inset] dark:shadow-[0px_0px_1px_3px_rgba(255,255,255,0.05)_inset]"
							}`}
						/>
					);
				})
			)}
		</div>
	);
}
