import { type CSSProperties, memo, type SVGProps, useId } from "react";

import { cn } from "@/lib/utils";

type DotMotionStyle = CSSProperties & {
	"--timeline-x": string;
	"--timeline-y": string;
	"--timeline-cross-x": string;
	"--timeline-cross-y": string;
	"--timeline-burst-x": string;
	"--timeline-burst-y": string;
	"--timeline-pulse-x": string;
	"--timeline-pulse-y": string;
	"--timeline-recoil-x": string;
	"--timeline-recoil-y": string;
	"--timeline-pulse-duration": string;
	"--timeline-pulse-delay": string;
	"--timeline-breathe-primary-delay": string;
	"--timeline-breathe-secondary-delay": string;
};

const DOTS = [
	{
		id: "east",
		pair: "a",
		x: 6.1,
		y: 0,
		burstX: 7.2,
		burstY: 0,
		pulseDuration: 1.92,
		pulseDelay: -0.35,
		breathePrimaryDelay: -3.96,
		breatheSecondaryDelay: 0,
	},
	{
		id: "south-east",
		pair: "b",
		x: 3.05,
		y: 5.28,
		burstX: 3.6,
		burstY: 6.24,
		pulseDuration: 2.18,
		pulseDelay: -1.15,
		breathePrimaryDelay: -0.506,
		breatheSecondaryDelay: -0.542,
	},
	{
		id: "south-west",
		pair: "c",
		x: -3.05,
		y: 5.28,
		burstX: -3.6,
		burstY: 6.24,
		pulseDuration: 2.43,
		pulseDelay: -0.6,
		breathePrimaryDelay: -3.867,
		breatheSecondaryDelay: -1.083,
	},
	{
		id: "west",
		pair: "a",
		x: -6.1,
		y: 0,
		burstX: -7.2,
		burstY: 0,
		pulseDuration: 2.06,
		pulseDelay: -1.7,
		breathePrimaryDelay: -3.043,
		breatheSecondaryDelay: -1.625,
	},
	{
		id: "north-west",
		pair: "b",
		x: -3.05,
		y: -5.28,
		burstX: -3.6,
		burstY: -6.24,
		pulseDuration: 2.31,
		pulseDelay: -0.95,
		breathePrimaryDelay: -3.763,
		breatheSecondaryDelay: -2.167,
	},
	{
		id: "north-east",
		pair: "c",
		x: 3.05,
		y: -5.28,
		burstX: 3.6,
		burstY: -6.24,
		pulseDuration: 2.54,
		pulseDelay: -2.1,
		breathePrimaryDelay: -2.719,
		breatheSecondaryDelay: -2.708,
	},
] as const;

const dotStyles = DOTS.map(
	({
		id,
		pair,
		x,
		y,
		burstX,
		burstY,
		pulseDuration,
		pulseDelay,
		breathePrimaryDelay,
		breatheSecondaryDelay,
	}) =>
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
				"--timeline-pulse-x": `${x * 0.075}px`,
				"--timeline-pulse-y": `${y * 0.075}px`,
				"--timeline-recoil-x": `${x * -0.0315}px`,
				"--timeline-recoil-y": `${y * -0.0315}px`,
				"--timeline-pulse-duration": `${pulseDuration}s`,
				"--timeline-pulse-delay": `${pulseDelay}s`,
				"--timeline-breathe-primary-delay": `${breathePrimaryDelay}s`,
				"--timeline-breathe-secondary-delay": `${breatheSecondaryDelay}s`,
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
			className={cn(
				"timeline-activity-indicator block size-6 shrink-0 overflow-visible",
				className
			)}
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
				<g className="timeline-activity-orbit">
					{dotStyles.map(({ id: dotId, pair, style }) => (
						<g
							key={dotId}
							className={`timeline-activity-dot timeline-activity-dot-${pair}`}
							style={style}
						>
							<g className="timeline-activity-pulse">
								<g className="timeline-activity-breathe-primary">
									<g className="timeline-activity-breathe-secondary">
										<circle cx="12" cy="12" r="1.7" />
									</g>
								</g>
							</g>
						</g>
					))}
				</g>
			</g>
			<g className="timeline-activity-light">
				<g className="timeline-activity-orbit">
					{dotStyles.map(({ id, pair, style }) => (
						<g
							key={id}
							className={`timeline-activity-dot timeline-activity-dot-${pair}`}
							style={style}
						>
							<g className="timeline-activity-pulse">
								<g className="timeline-activity-breathe-primary">
									<g className="timeline-activity-breathe-secondary">
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
								</g>
							</g>
						</g>
					))}
				</g>
			</g>
		</svg>
	);
});
