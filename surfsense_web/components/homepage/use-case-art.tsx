"use client";

import { motion, useReducedMotion } from "motion/react";

const EASE_OUT: [number, number, number, number] = [0.16, 1, 0.3, 1];
const VIEWPORT = { once: true, amount: 0.4 } as const;

export type UseCaseArtVariant = "price" | "brand" | "leads" | "serp";

/** Soft infinite pulse ring marking the "live" signal in each artifact. */
function Pulse({
	cx,
	cy,
	reduce,
	delay = 0,
}: {
	cx: number;
	cy: number;
	reduce: boolean;
	delay?: number;
}) {
	if (reduce) return null;
	return (
		<motion.circle
			cx={cx}
			cy={cy}
			r={5}
			className="fill-brand/40"
			style={{ transformBox: "fill-box", transformOrigin: "center" }}
			animate={{ scale: [1, 2.4], opacity: [0.5, 0] }}
			transition={{ duration: 2, ease: "easeOut", repeat: Infinity, delay }}
		/>
	);
}

/** Competitor price monitoring: a price line steps up; the change point alerts. */
function PriceArt({ reduce }: { reduce: boolean }) {
	return (
		<motion.svg
			viewBox="0 0 240 96"
			className="h-auto w-full"
			initial={reduce ? undefined : "hidden"}
			whileInView="visible"
			viewport={VIEWPORT}
		>
			{/* Grid */}
			{[24, 48, 72].map((y) => (
				<line
					key={y}
					x1="12"
					y1={y}
					x2="228"
					y2={y}
					className="stroke-muted-foreground/15"
					strokeWidth="1"
				/>
			))}
			{/* Price line with a step change at x=132 */}
			<motion.path
				d="M 12 66 L 56 64 L 96 62 L 132 62 L 132 38 L 176 36 L 228 34"
				fill="none"
				className="stroke-brand"
				strokeWidth="2"
				strokeLinecap="round"
				variants={{ hidden: { pathLength: 0 }, visible: { pathLength: 1 } }}
				transition={{ duration: 0.9, ease: EASE_OUT }}
			/>
			{/* Alert at the step */}
			<Pulse cx={132} cy={38} reduce={reduce} delay={0.9} />
			<motion.circle
				cx="132"
				cy="38"
				r="4"
				className="fill-brand"
				variants={{ hidden: { opacity: 0, scale: 0 }, visible: { opacity: 1, scale: 1 } }}
				style={{ transformBox: "fill-box", transformOrigin: "center" }}
				transition={{ duration: 0.3, ease: EASE_OUT, delay: 0.7 }}
			/>
			{/* Price-change tag */}
			<motion.g
				variants={{ hidden: { opacity: 0, y: 6 }, visible: { opacity: 1, y: 0 } }}
				transition={{ duration: 0.3, ease: EASE_OUT, delay: 0.85 }}
			>
				<rect x="146" y="46" width="52" height="18" rx="4" className="fill-brand/10" />
				<text x="172" y="59" textAnchor="middle" className="fill-brand text-[10px] font-medium">
					+$10/mo
				</text>
			</motion.g>
		</motion.svg>
	);
}

/** Brand monitoring: a listening radar; mentions blip in around the brand. */
function BrandArt({ reduce }: { reduce: boolean }) {
	const blips = [
		{ cx: 84, cy: 30, delay: 0.5 },
		{ cx: 168, cy: 38, delay: 0.7 },
		{ cx: 100, cy: 70, delay: 0.9 },
	];
	return (
		<motion.svg
			viewBox="0 0 240 96"
			className="h-auto w-full"
			initial={reduce ? undefined : "hidden"}
			whileInView="visible"
			viewport={VIEWPORT}
		>
			{/* Radar rings */}
			{[16, 30, 44].map((r, i) => (
				<motion.circle
					key={r}
					cx="120"
					cy="48"
					r={r}
					fill="none"
					className="stroke-muted-foreground/20"
					strokeWidth="1"
					variants={{ hidden: { opacity: 0, scale: 0.6 }, visible: { opacity: 1, scale: 1 } }}
					style={{ transformBox: "fill-box", transformOrigin: "center" }}
					transition={{ duration: 0.45, ease: EASE_OUT, delay: i * 0.12 }}
				/>
			))}
			{/* Brand at the center */}
			<motion.circle
				cx="120"
				cy="48"
				r="4"
				className="fill-brand"
				variants={{ hidden: { opacity: 0, scale: 0 }, visible: { opacity: 1, scale: 1 } }}
				style={{ transformBox: "fill-box", transformOrigin: "center" }}
				transition={{ duration: 0.3, ease: EASE_OUT, delay: 0.35 }}
			/>
			<Pulse cx={120} cy={48} reduce={reduce} delay={0.6} />
			{/* Mention blips */}
			{blips.map((blip) => (
				<motion.circle
					key={`${blip.cx}-${blip.cy}`}
					cx={blip.cx}
					cy={blip.cy}
					r="3"
					className="fill-brand/70"
					variants={{ hidden: { opacity: 0, scale: 0 }, visible: { opacity: 1, scale: 1 } }}
					style={{ transformBox: "fill-box", transformOrigin: "center" }}
					transition={{ duration: 0.3, ease: EASE_OUT, delay: blip.delay }}
				/>
			))}
		</motion.svg>
	);
}

/** B2B lead generation: a lead list fills in row by row, each verified. */
function LeadsArt({ reduce }: { reduce: boolean }) {
	const rows = [22, 48, 74];
	return (
		<motion.svg
			viewBox="0 0 240 96"
			className="h-auto w-full"
			initial={reduce ? undefined : "hidden"}
			whileInView="visible"
			viewport={VIEWPORT}
		>
			{rows.map((y, i) => (
				<motion.g
					key={y}
					variants={{ hidden: { opacity: 0, x: -10 }, visible: { opacity: 1, x: 0 } }}
					transition={{ duration: 0.35, ease: EASE_OUT, delay: 0.15 + i * 0.18 }}
				>
					{/* Avatar */}
					<circle cx="24" cy={y} r="7" className="fill-muted-foreground/20" />
					{/* Name + contact lines */}
					<rect
						x="40"
						y={y - 8}
						width="92"
						height="6"
						rx="3"
						className="fill-muted-foreground/30"
					/>
					<rect
						x="40"
						y={y + 3}
						width="64"
						height="5"
						rx="2.5"
						className="fill-muted-foreground/15"
					/>
					{/* Verified check */}
					<motion.path
						d={`M 206 ${y - 1} l 4 5 l 8 -10`}
						fill="none"
						className="stroke-brand"
						strokeWidth="2.5"
						strokeLinecap="round"
						strokeLinejoin="round"
						variants={{
							hidden: { pathLength: 0, opacity: 0 },
							visible: { pathLength: 1, opacity: 1 },
						}}
						transition={{ duration: 0.3, ease: EASE_OUT, delay: 0.45 + i * 0.18 }}
					/>
				</motion.g>
			))}
		</motion.svg>
	);
}

/** Market research: SERP rows; your result climbs from #3 to #1. */
function SerpArt({ reduce }: { reduce: boolean }) {
	const swapDelay = 0.8;
	const swapY = { duration: 0.5, ease: EASE_OUT, delay: swapDelay, times: [0, 0.6, 1] };
	return (
		<motion.svg
			viewBox="0 0 240 96"
			className="h-auto w-full"
			initial={reduce ? undefined : "hidden"}
			whileInView="visible"
			viewport={VIEWPORT}
		>
			{/* Competitor rows: start at ranks 1 and 2, shift down one slot */}
			{[
				{ startY: 14, width: 148 },
				{ startY: 40, width: 120 },
			].map((row, i) => (
				<motion.g
					key={row.startY}
					style={reduce ? { y: 26 } : undefined}
					variants={
						reduce
							? undefined
							: { hidden: { opacity: 0, y: 0 }, visible: { opacity: 1, y: [0, 0, 26] } }
					}
					transition={
						reduce
							? undefined
							: { opacity: { duration: 0.35, ease: EASE_OUT, delay: 0.1 + i * 0.15 }, y: swapY }
					}
				>
					<rect
						x="34"
						y={row.startY}
						width={row.width}
						height="8"
						rx="4"
						className="fill-muted-foreground/25"
					/>
					<rect
						x="34"
						y={row.startY + 12}
						width={row.width * 0.6}
						height="5"
						rx="2.5"
						className="fill-muted-foreground/12"
					/>
				</motion.g>
			))}
			{/* Your row: starts at rank 3, climbs to rank 1 */}
			<motion.g
				style={reduce ? { y: -52 } : undefined}
				variants={
					reduce
						? undefined
						: { hidden: { opacity: 0, y: 0 }, visible: { opacity: 1, y: [0, 0, -52] } }
				}
				transition={
					reduce ? undefined : { opacity: { duration: 0.35, ease: EASE_OUT, delay: 0.4 }, y: swapY }
				}
			>
				<rect x="34" y="66" width="160" height="8" rx="4" className="fill-brand" />
				<rect x="34" y="78" width="96" height="5" rx="2.5" className="fill-brand/40" />
				<motion.path
					d="M 210 78 l 5 -7 l 5 7"
					fill="none"
					className="stroke-brand"
					strokeWidth="2.5"
					strokeLinecap="round"
					strokeLinejoin="round"
					variants={reduce ? undefined : { hidden: { opacity: 0 }, visible: { opacity: 1 } }}
					transition={{ duration: 0.3, ease: EASE_OUT, delay: swapDelay }}
				/>
			</motion.g>
		</motion.svg>
	);
}

const ART: Record<UseCaseArtVariant, (props: { reduce: boolean }) => React.ReactNode> = {
	price: PriceArt,
	brand: BrandArt,
	leads: LeadsArt,
	serp: SerpArt,
};

/** Small animated artifact rendered at the top of each use-case card. */
export function UseCaseArt({ variant }: { variant: UseCaseArtVariant }) {
	const reduce = useReducedMotion() ?? false;
	const Art = ART[variant];
	return (
		<div aria-hidden className="mb-4 rounded-lg border bg-muted/20 px-3 py-2">
			<Art reduce={reduce} />
		</div>
	);
}
