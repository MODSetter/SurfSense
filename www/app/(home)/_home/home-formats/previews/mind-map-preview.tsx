// Branch ends in the 240×120 viewBox; the root sits at its centre.
const BRANCHES = [
	{ x: 40, y: 24 },
	{ x: 40, y: 96 },
	{ x: 200, y: 24 },
	{ x: 200, y: 96 },
];

/** A root concept with four linked branches. */
export function MindMapPreview() {
	return (
		<svg aria-hidden="true" viewBox="0 0 240 120" className="w-full max-w-sm">
			{BRANCHES.map((branch) => (
				<path
					key={`${branch.x}-${branch.y}`}
					d={`M120 60 C ${(120 + branch.x) / 2} 60, ${(120 + branch.x) / 2} ${branch.y}, ${branch.x} ${branch.y}`}
					className="fill-none stroke-(--notice)/50"
					strokeWidth={1.5}
				/>
			))}
			{BRANCHES.map((branch) => (
				<rect
					key={`${branch.x}-${branch.y}`}
					x={branch.x - 28}
					y={branch.y - 10}
					width={56}
					height={20}
					rx={10}
					className="fill-card stroke-black/10"
				/>
			))}
			<rect x={84} y={46} width={72} height={28} rx={14} className="fill-(--notice)" />
			<rect x={100} y={57} width={40} height={6} rx={3} className="fill-white/80" />
		</svg>
	);
}
