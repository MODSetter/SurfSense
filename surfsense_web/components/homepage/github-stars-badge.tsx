"use client";

import * as React from "react";
import {
	motion,
	AnimatePresence,
	useInView,
	useMotionValue,
	useSpring,
	useTransform,
} from "motion/react";
import type { HTMLMotionProps, UseInViewOptions } from "motion/react";
import { StarIcon } from "lucide-react";
import { IconBrandGithub } from "@tabler/icons-react";
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
// Particles (for star burst effect on completion)
// ---------------------------------------------------------------------------
type ParticlesContextType = { animate: boolean; isInView: boolean };
const [ParticlesProvider, useParticles] =
	getStrictContext<ParticlesContextType>("ParticlesContext");

function Particles({
	ref,
	animate = true,
	inView = false,
	inViewMargin = "0px",
	inViewOnce = true,
	children,
	style,
	...props
}: Omit<HTMLMotionProps<"div">, "children"> & {
	animate?: boolean;
	children: React.ReactNode;
} & UseIsInViewOptions) {
	const { ref: localRef, isInView } = useIsInView(ref as React.Ref<HTMLDivElement>, {
		inView,
		inViewOnce,
		inViewMargin,
	});
	return (
		<ParticlesProvider value={{ animate, isInView }}>
			<motion.div ref={localRef} style={{ position: "relative", ...style }} {...props}>
				{children}
			</motion.div>
		</ParticlesProvider>
	);
}

function ParticlesEffect({
	side = "top",
	align = "center",
	count = 6,
	radius = 30,
	spread = 360,
	duration = 0.8,
	holdDelay = 0.05,
	sideOffset = 0,
	alignOffset = 0,
	delay = 0,
	transition,
	style,
	...props
}: Omit<HTMLMotionProps<"div">, "children"> & {
	side?: "top" | "bottom" | "left" | "right";
	align?: "start" | "center" | "end";
	count?: number;
	radius?: number;
	spread?: number;
	duration?: number;
	holdDelay?: number;
	sideOffset?: number;
	alignOffset?: number;
	delay?: number;
}) {
	const { animate, isInView } = useParticles();
	const isVertical = side === "top" || side === "bottom";
	const alignPct = align === "start" ? "0%" : align === "end" ? "100%" : "50%";

	const top = isVertical
		? side === "top"
			? `calc(0% - ${sideOffset}px)`
			: `calc(100% + ${sideOffset}px)`
		: `calc(${alignPct} + ${alignOffset}px)`;
	const left = isVertical
		? `calc(${alignPct} + ${alignOffset}px)`
		: side === "left"
			? `calc(0% - ${sideOffset}px)`
			: `calc(100% + ${sideOffset}px)`;

	const containerStyle: React.CSSProperties = {
		position: "absolute",
		top,
		left,
		transform: "translate(-50%, -50%)",
	};
	const angleStep = (spread * (Math.PI / 180)) / Math.max(1, count - 1);

	return (
		<AnimatePresence>
			{animate &&
				isInView &&
				[...Array(count)].map((_, i) => {
					const angle = i * angleStep;
					const x = Math.cos(angle) * radius;
					const y = Math.sin(angle) * radius;
					return (
						<motion.div
							key={`particle-${angle}`}
							style={{ ...containerStyle, ...style }}
							initial={{ scale: 0, opacity: 0 }}
							animate={{
								x: `${x}px`,
								y: `${y}px`,
								scale: [0, 1, 0],
								opacity: [0, 1, 0],
							}}
							transition={{
								duration,
								delay: delay + i * holdDelay,
								ease: "easeOut",
								...transition,
							}}
							{...props}
						/>
					);
				})}
		</AnimatePresence>
	);
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
	const [stars, setStars] = React.useState(0);
	const [isLoading, setIsLoading] = React.useState(true);
	const [isCompleted, setIsCompleted] = React.useState(false);

	const fillRaw = useMotionValue(0);
	const fillSpring = useSpring(fillRaw, { stiffness: 12, damping: 14 });
	const clipPath = useTransform(fillSpring, (v) => `inset(${100 - v * 100}% 0 0 0)`);

	React.useEffect(() => {
		const abortController = new AbortController();
		fetch(`https://api.github.com/repos/${username}/${repo}`, {
			signal: abortController.signal,
		})
			.then((res) => res.json())
			.then((data) => {
				if (data && typeof data.stargazers_count === "number") {
					setStars(data.stargazers_count);
					fillRaw.set(1);
				}
			})
			.catch((err) => {
				if (err instanceof Error && err.name !== "AbortError") {
					console.error("Error fetching stars:", err);
				}
			})
			.finally(() => setIsLoading(false));
		return () => abortController.abort();
	}, [username, repo, fillRaw]);

	return (
		<a
			href={href}
			target="_blank"
			rel="noopener noreferrer"
			className={cn(
				"group flex items-center gap-2 rounded-full px-3 py-1.5 transition-colors",
				className
			)}
		>
			<IconBrandGithub className="h-5 w-5 text-neutral-600 dark:text-neutral-300 shrink-0" />
			<div className="flex items-center gap-1 rounded-md bg-neutral-100 dark:bg-neutral-800 group-hover:bg-neutral-200 dark:group-hover:bg-neutral-700 px-2 py-0.5 transition-colors">
				<AnimatedStarCount
					value={isLoading ? 10000 : stars}
					itemSize={ITEM_SIZE}
					isRolling={isLoading}
					className="text-sm font-semibold tabular-nums text-neutral-500 dark:text-neutral-400 group-hover:text-neutral-800 dark:group-hover:text-neutral-200 transition-colors"
					onComplete={() => setIsCompleted(true)}
				/>
				<Particles animate={isCompleted}>
					<div className="relative size-4">
						<StarIcon
							aria-hidden="true"
							className="absolute inset-0 size-4 fill-neutral-400 stroke-neutral-400 dark:fill-neutral-700 dark:stroke-neutral-700 group-hover:fill-neutral-600 group-hover:stroke-neutral-600 dark:group-hover:fill-neutral-300 dark:group-hover:stroke-neutral-300 transition-colors"
						/>
						<motion.div className="absolute inset-0" style={{ clipPath }}>
							<StarIcon
								aria-hidden="true"
								className="size-4 fill-neutral-300 stroke-neutral-300 dark:fill-neutral-400 dark:stroke-neutral-400 group-hover:fill-neutral-500 group-hover:stroke-neutral-500 dark:group-hover:fill-neutral-200 dark:group-hover:stroke-neutral-200 transition-colors"
							/>
						</motion.div>
					</div>
					<ParticlesEffect
						delay={0.3}
						className="size-1 rounded-full bg-neutral-300 dark:bg-neutral-400"
					/>
				</Particles>
			</div>
		</a>
	);
}

export { NavbarGitHubStars, type NavbarGitHubStarsProps };
