"use client";

import { IconBrandGithub } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { motion, useMotionValue, useSpring } from "motion/react";
import * as React from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { cacheKeys } from "@/lib/query-client/cache-keys";

// ---------------------------------------------------------------------------
// Per-digit scrolling wheel
// ---------------------------------------------------------------------------
const ROLLING_ITEM_COUNT = 200;

function DigitWheel({
	digit,
	itemSize = 22,
	delay = 0,
	cycles = 5,
	isRolling = false,
	reverse = false,
	className,
	onSettled,
}: {
	digit: number;
	itemSize?: number;
	delay?: number;
	cycles?: number;
	isRolling?: boolean;
	reverse?: boolean;
	className?: string;
	onSettled?: () => void;
}) {
	const sequence = React.useMemo(() => {
		if (isRolling) {
			return Array.from({ length: ROLLING_ITEM_COUNT }, (_, i) => ({
				id: `r${i}`,
				value: i % 10,
			}));
		}

		const seq = Array.from({ length: cycles * 10 }, (_, i) => ({
			id: `s${i}`,
			value: (i * 7 + 3) % 10,
		}));
		const target = { id: "target", value: digit };
		if (reverse) {
			seq.unshift(target);
		} else {
			seq.push(target);
		}
		return seq;
	}, [digit, cycles, isRolling, reverse]);

	const maxOffset = (sequence.length - 1) * itemSize;
	const endY = reverse ? 0 : -maxOffset;

	const rollingStartItem = React.useRef(0);
	const startOffset = rollingStartItem.current * itemSize;

	const y = useMotionValue(
		isRolling ? (reverse ? -(maxOffset - startOffset) : -startOffset) : reverse ? -maxOffset : 0
	);
	const ySpring = useSpring(
		y,
		isRolling ? { stiffness: 10000, damping: 500 } : { stiffness: 70, damping: 20 }
	);
	const settledRef = React.useRef(false);
	const wasRollingRef = React.useRef(isRolling);

	// Jump y to settling start position when transitioning from rolling → settled
	React.useLayoutEffect(() => {
		if (wasRollingRef.current && !isRolling) {
			y.jump(reverse ? -maxOffset : 0);
		}
		wasRollingRef.current = isRolling;
	}, [isRolling, reverse, maxOffset, y]);

	// Rolling: drive y continuously via RAF (stiff spring tracks it transparently)
	React.useEffect(() => {
		if (!isRolling) return;

		const cycleHeight = 10 * itemSize;
		const msPerCycle = 1000;
		let startTime: number | null = null;
		let rafId: number;

		const tick = (time: number) => {
			if (startTime === null) startTime = time;
			const elapsed = time - startTime;
			const speed = cycleHeight / msPerCycle;
			const travel = elapsed * speed + startOffset;

			if (reverse) {
				y.set(Math.min(-maxOffset + travel, 0));
			} else {
				y.set(Math.max(-travel, -maxOffset));
			}

			rafId = requestAnimationFrame(tick);
		};

		rafId = requestAnimationFrame(tick);
		return () => cancelAnimationFrame(rafId);
	}, [isRolling, itemSize, reverse, y, maxOffset, startOffset]);

	// Settling: spring to endY after delay
	React.useEffect(() => {
		if (isRolling) return;
		settledRef.current = false;
		const timer = setTimeout(() => y.set(endY), delay);
		return () => clearTimeout(timer);
	}, [endY, y, delay, isRolling]);

	// Detect settled
	React.useEffect(() => {
		if (isRolling) return;
		const unsub = ySpring.on("change", (latest) => {
			if (!settledRef.current && Math.abs(latest - endY) < 0.5) {
				settledRef.current = true;
				onSettled?.();
			}
		});
		return unsub;
	}, [ySpring, endY, onSettled, isRolling]);

	return (
		<div style={{ height: itemSize, overflow: "hidden" }}>
			<motion.div style={{ y: ySpring }}>
				{sequence.map((item) => (
					<div
						key={item.id}
						className={className}
						style={{
							height: itemSize,
							display: "flex",
							alignItems: "center",
							justifyContent: "center",
						}}
					>
						{item.value}
					</div>
				))}
			</motion.div>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Animated star count with per-digit alternating wheels
// ---------------------------------------------------------------------------
const numberFormatter = new Intl.NumberFormat("en-US");

function AnimatedStarCount({
	value,
	itemSize = 22,
	isRolling = false,
	className,
	onComplete,
}: {
	value: number;
	itemSize?: number;
	isRolling?: boolean;
	className?: string;
	onComplete?: () => void;
}) {
	const formatted = numberFormatter.format(value);
	const chars = formatted.split("");

	let totalDigits = 0;
	for (const c of chars) {
		if (c >= "0" && c <= "9") totalDigits++;
	}

	const settledCount = React.useRef(0);
	const completedRef = React.useRef(false);

	const handleDigitSettled = React.useCallback(() => {
		settledCount.current++;
		if (!completedRef.current && settledCount.current >= totalDigits) {
			completedRef.current = true;
			onComplete?.();
		}
	}, [totalDigits, onComplete]);

	let digitIndex = 0;
	let separatorIndex = 0;

	return (
		<div className="flex items-center">
			{chars.map((char) => {
				if (char < "0" || char > "9") {
					const sepKey = `sep-${separatorIndex++}`;
					return (
						<div
							key={sepKey}
							className={className}
							style={{
								height: itemSize,
								display: "flex",
								alignItems: "center",
								justifyContent: "center",
								width: "0.3em",
							}}
						>
							{char}
						</div>
					);
				}
				const digit = parseInt(char, 10);
				const idx = digitIndex++;
				return (
					<DigitWheel
						key={`digit-${idx}`}
						digit={digit}
						itemSize={itemSize}
						delay={idx * 150}
						cycles={5}
						isRolling={isRolling}
						reverse={idx % 2 === 1}
						className={className}
						onSettled={handleDigitSettled}
					/>
				);
			})}
		</div>
	);
}

// ---------------------------------------------------------------------------
// NavbarGitHubStars — the exported component
// ---------------------------------------------------------------------------
const ITEM_SIZE = 22;

type NavbarGitHubStarsProps = {
	username?: string;
	repo?: string;
	href?: string;
	className?: string;
};

function NavbarGitHubStars({
	username = "MODSetter",
	repo = "SurfSense",
	href = "https://github.com/MODSetter/SurfSense",
	className,
}: NavbarGitHubStarsProps) {
	const { data: stars = 0, isLoading } = useQuery({
		queryKey: cacheKeys.github.repoStars(username, repo),
		queryFn: async ({ signal }) => {
			const res = await fetch(
				`https://api.github.com/repos/${username}/${repo}`,
				{ signal },
			);
			const data = await res.json();
			if (data && typeof data.stargazers_count === "number") {
				return data.stargazers_count as number;
			}
			return 0;
		},
		staleTime: 5 * 60 * 1000,
	});

	return (
		<a
			href={href}
			target="_blank"
			rel="noopener noreferrer"
			className={cn(
				"group flex items-center gap-1 rounded-lg px-2 py-1 hover:bg-gray-100 dark:hover:bg-neutral-800/50 transition-colors",
				className
			)}
		>
			<IconBrandGithub className="h-5 w-5 text-neutral-700 dark:text-neutral-300 shrink-0" />
			{isLoading ? (
				<Skeleton className="h-4 w-10" />
			) : (
				<AnimatedStarCount
					value={stars}
					itemSize={ITEM_SIZE}
					isRolling={false}
					className="text-sm font-semibold tabular-nums text-neutral-700 dark:text-neutral-300 group-hover:text-neutral-900 dark:group-hover:text-neutral-100 transition-colors"
				/>
			)}
		</a>
	);
}

export { NavbarGitHubStars, type NavbarGitHubStarsProps };
