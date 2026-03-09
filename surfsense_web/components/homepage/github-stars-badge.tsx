"use client";

import { IconBrandGithub } from "@tabler/icons-react";
import type { HTMLMotionProps, UseInViewOptions } from "motion/react";
import { motion, useInView, useMotionValue, useSpring } from "motion/react";
import * as React from "react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function getStrictContext<T>(name?: string) {
	const Context = React.createContext<T | undefined>(undefined);
	const Provider = ({ value, children }: { value: T; children?: React.ReactNode }) => (
		<Context.Provider value={value}>{children}</Context.Provider>
	);
	const useSafeContext = () => {
		const ctx = React.useContext(Context);
		if (ctx === undefined) {
			throw new Error(`useContext must be used within ${name ?? "a Provider"}`);
		}
		return ctx;
	};
	return [Provider, useSafeContext] as const;
}

interface UseIsInViewOptions {
	inView?: boolean;
	inViewOnce?: boolean;
	inViewMargin?: UseInViewOptions["margin"];
}

function useIsInView<T extends HTMLElement = HTMLElement>(
	ref: React.Ref<T>,
	options: UseIsInViewOptions = {}
) {
	const { inView, inViewOnce = false, inViewMargin = "0px" } = options;
	const localRef = React.useRef<T>(null);
	React.useImperativeHandle(ref, () => localRef.current as T);
	const inViewResult = useInView(localRef, {
		once: inViewOnce,
		margin: inViewMargin,
	});
	const isInView = !inView || inViewResult;
	return { ref: localRef, isInView };
}

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
			value: Math.floor(Math.random() * 10),
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

	const rollingStartItem = React.useRef(Math.floor(Math.random() * 10));
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
	animated = true,
	className,
	onComplete,
}: {
	value: number;
	itemSize?: number;
	isRolling?: boolean;
	animated?: boolean;
	className?: string;
	onComplete?: () => void;
}) {
	const formatted = numberFormatter.format(value);
	const chars = formatted.split("");

	if (!animated) {
		return (
			<div className="flex items-center">
				{chars.map((char, idx) => (
					<div
						key={`static-${idx}-${char}`}
						className={className}
						style={{
							height: itemSize,
							display: "flex",
							alignItems: "center",
							justifyContent: "center",
							width: char >= "0" && char <= "9" ? undefined : "0.3em",
						}}
					>
						{char}
					</div>
				))}
			</div>
		);
	}

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
	const [hasMounted, setHasMounted] = React.useState(false);
	const [stars, setStars] = React.useState(0);
	const [isLoading, setIsLoading] = React.useState(true);

	React.useEffect(() => {
		setHasMounted(true);
	}, []);

	React.useEffect(() => {
		const abortController = new AbortController();
		fetch(`https://api.github.com/repos/${username}/${repo}`, {
			signal: abortController.signal,
		})
			.then((res) => res.json())
			.then((data) => {
				if (data && typeof data.stargazers_count === "number") {
					setStars(data.stargazers_count);
				}
			})
			.catch((err) => {
				if (err instanceof Error && err.name !== "AbortError") {
					console.error("Error fetching stars:", err);
				}
			})
			.finally(() => setIsLoading(false));
		return () => abortController.abort();
	}, [username, repo]);

	return (
		<a
			href={href}
			target="_blank"
			rel="noopener noreferrer"
			className={cn(
				"group inline-flex items-center rounded-full border border-neutral-200 bg-white/80 px-3 py-1.5 text-sm backdrop-blur-sm transition-colors dark:border-neutral-800 dark:bg-neutral-950/80",
				"hover:bg-neutral-100 dark:hover:bg-neutral-900",
				className
			)}
		>
			<IconBrandGithub className="h-5 w-5 shrink-0 text-neutral-600 transition-colors dark:text-neutral-300 group-hover:text-neutral-800 dark:group-hover:text-neutral-100" />
			<div className="ml-2 flex items-center text-neutral-500 transition-colors dark:text-neutral-400 group-hover:text-neutral-800 dark:group-hover:text-neutral-200">
				<AnimatedStarCount
					value={isLoading ? 10000 : stars}
					itemSize={ITEM_SIZE}
					isRolling={hasMounted && isLoading}
					animated={hasMounted}
					className="text-sm font-semibold tabular-nums text-neutral-500 dark:text-neutral-400 group-hover:text-neutral-800 dark:group-hover:text-neutral-200 transition-colors"
				/>
			</div>
		</a>
	);
}

export { NavbarGitHubStars, type NavbarGitHubStarsProps };
