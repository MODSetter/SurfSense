import { type CSSProperties, memo, type SVGProps, useId } from "react";

import { cn } from "@/lib/utils";

type DotMotionStyle = CSSProperties & {
	"--timeline-x": string;
	"--timeline-y": string;
	"--timeline-cross-x": string;
	"--timeline-cross-y": string;
	"--timeline-burst-x": string;
	"--timeline-burst-y": string;
};

const DOTS = [
	{ id: "east", pair: "a", x: 6.1, y: 0, burstX: 7.2, burstY: 0 },
	{ id: "south-east", pair: "b", x: 3.05, y: 5.28, burstX: 3.6, burstY: 6.24 },
	{ id: "south-west", pair: "c", x: -3.05, y: 5.28, burstX: -3.6, burstY: 6.24 },
	{ id: "west", pair: "a", x: -6.1, y: 0, burstX: -7.2, burstY: 0 },
	{ id: "north-west", pair: "b", x: -3.05, y: -5.28, burstX: -3.6, burstY: -6.24 },
	{ id: "north-east", pair: "c", x: 3.05, y: -5.28, burstX: 3.6, burstY: -6.24 },
] as const;

const dotStyles = DOTS.map(
	({ id, pair, x, y, burstX, burstY }) =>
		({
			id,
			pair,
			style: {
				"--timeline-x": `${x}px`,
				"--timeline-y": `${y}px`,
				"--timeline-cross-x": `${-x}px`,
				"--timeline-cross-y": `${-y}px`,
				"--timeline-burst-x": `${burstX}px`,
				"--timeline-burst-y": `${burstY}px`,
			} as DotMotionStyle,
		}) as const
);

export type TimelineActivityIndicatorProps = Omit<SVGProps<SVGSVGElement>, "children">;

export const TimelineActivityIndicator = memo(function TimelineActivityIndicator({
	className,
	...props
}: TimelineActivityIndicatorProps) {
	const id = useId();
	const bloomFilterId = `${id}-timeline-activity-bloom`;
	const fringeFilterId = `${id}-timeline-activity-fringe`;
	const gooFilterId = `${id}-timeline-activity-goo`;

	return (
		<svg
			{...props}
			aria-hidden="true"
			className={cn("timeline-activity-indicator block size-6 shrink-0", className)}
			focusable="false"
			viewBox="0 0 24 24"
		>
			<defs>
				<filter
					id={bloomFilterId}
					x="-150%"
					y="-150%"
					width="400%"
					height="400%"
					colorInterpolationFilters="sRGB"
				>
					<feGaussianBlur stdDeviation="1.65" />
				</filter>
				<filter
					id={fringeFilterId}
					x="-80%"
					y="-80%"
					width="260%"
					height="260%"
					colorInterpolationFilters="sRGB"
				>
					<feGaussianBlur stdDeviation="0.55" />
				</filter>
				<filter
					id={gooFilterId}
					x="-50%"
					y="-50%"
					width="200%"
					height="200%"
					colorInterpolationFilters="sRGB"
				>
					<feGaussianBlur in="SourceGraphic" stdDeviation="0.8" result="blur" />
					<feColorMatrix
						in="blur"
						type="matrix"
						values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 15 -5.5"
					/>
				</filter>
			</defs>
			<g className="timeline-activity-goo" fill="#fff" filter={`url(#${gooFilterId})`}>
				{dotStyles.map(({ id: dotId, pair, style }) => (
					<circle
						key={dotId}
						className={`timeline-activity-dot timeline-activity-dot-${pair}`}
						cx="12"
						cy="12"
						r="1.7"
						style={style}
					/>
				))}
			</g>
			<g className="timeline-activity-light">
				{dotStyles.map(({ id, pair, style }) => (
					<g
						key={id}
						className={`timeline-activity-dot timeline-activity-dot-${pair}`}
						style={style}
					>
						<circle
							cx="12"
							cy="12"
							r="2.15"
							fill="#dce8f0"
							opacity="0.42"
							filter={`url(#${bloomFilterId})`}
						/>
						<circle
							cx="11.68"
							cy="12.06"
							r="1.85"
							fill="#9de5ff"
							opacity="0.62"
							filter={`url(#${fringeFilterId})`}
						/>
						<circle
							cx="12.32"
							cy="12.06"
							r="1.85"
							fill="#ffd2a0"
							opacity="0.58"
							filter={`url(#${fringeFilterId})`}
						/>
						<circle cx="12" cy="12" r="1.58" fill="#fff" />
					</g>
				))}
			</g>
		</svg>
	);
});
