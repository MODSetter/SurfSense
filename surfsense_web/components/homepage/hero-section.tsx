"use client";
import { useFeatureFlagVariantKey } from "@posthog/react";
import { AnimatePresence, motion } from "motion/react";
import Image from "next/image";
import Link from "next/link";
import React, { useEffect, useRef, useState } from "react";
import Balancer from "react-wrap-balancer";
import { AUTH_TYPE, BACKEND_URL } from "@/lib/env-config";
import { trackLoginAttempt } from "@/lib/posthog/events";
import { cn } from "@/lib/utils";

// Official Google "G" logo with brand colors
const GoogleLogo = ({ className }: { className?: string }) => (
	<svg className={className} viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
		<path
			d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
			fill="#4285F4"
		/>
		<path
			d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
			fill="#34A853"
		/>
		<path
			d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
			fill="#FBBC05"
		/>
		<path
			d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
			fill="#EA4335"
		/>
	</svg>
);

export function HeroSection() {
	const containerRef = useRef<HTMLDivElement>(null);
	const parentRef = useRef<HTMLDivElement>(null);
	const heroVariant = useFeatureFlagVariantKey("notebooklm_flag");
	const isNotebookLMVariant = heroVariant === "notebooklm";

	return (
		<div
			ref={parentRef}
			className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-4 py-20 md:px-8 md:py-40"
		>
			<BackgroundGrids />
			<CollisionMechanism
				beamOptions={{
					initialX: -400,
					translateX: 600,
					duration: 7,
					repeatDelay: 3,
				}}
				containerRef={containerRef}
				parentRef={parentRef}
			/>
			<CollisionMechanism
				beamOptions={{
					initialX: -200,
					translateX: 800,
					duration: 4,
					repeatDelay: 3,
				}}
				containerRef={containerRef}
				parentRef={parentRef}
			/>
			<CollisionMechanism
				beamOptions={{
					initialX: 200,
					translateX: 1200,
					duration: 5,
					repeatDelay: 3,
				}}
				containerRef={containerRef}
				parentRef={parentRef}
			/>
			<CollisionMechanism
				containerRef={containerRef}
				parentRef={parentRef}
				beamOptions={{
					initialX: 400,
					translateX: 1400,
					duration: 6,
					repeatDelay: 3,
				}}
			/>

			<h2 className="relative z-50 mx-auto mb-4 mt-4 max-w-4xl text-balance text-center text-3xl font-semibold tracking-tight text-gray-700 md:text-7xl dark:text-neutral-300">
				<Balancer>
					{isNotebookLMVariant ? (
						<div className="relative mx-auto inline-block w-max filter-[drop-shadow(0px_1px_3px_rgba(27,37,80,0.14))]">
							<div className="text-black [text-shadow:0_0_rgba(0,0,0,0.1)] dark:text-white">
								<span className="">NotebookLM for Teams</span>
							</div>
						</div>
					) : (
						<>
							The AI Workspace{" "}
							<div className="relative mx-auto inline-block w-max filter-[drop-shadow(0px_1px_3px_rgba(27,37,80,0.14))]">
								<div className="text-black [text-shadow:0_0_rgba(0,0,0,0.1)] dark:text-white">
									<span className="">Built for Teams</span>
								</div>
							</div>
						</>
					)}
				</Balancer>
			</h2>
			{/* // TODO:aCTUAL DESCRITION */}
			<p className="relative z-50 mx-auto mt-4 max-w-lg px-4 text-center text-base/6 text-gray-600 dark:text-gray-200">
				Connect any LLM to your internal knowledge sources and chat with it in real time alongside
				your team.
			</p>
			<div className="mb-10 mt-8 flex w-full flex-col items-center justify-center gap-4 px-8 sm:flex-row md:mb-20">
				<GetStartedButton />
				<ContactSalesButton />
			</div>
			<div
				ref={containerRef}
				className="relative mx-auto max-w-7xl rounded-[32px] border border-neutral-200/50 bg-neutral-100 p-2 backdrop-blur-lg md:p-4 dark:border-neutral-700 dark:bg-neutral-800/50"
			>
				<div className="rounded-[24px] border border-neutral-200 bg-white p-2 dark:border-neutral-700 dark:bg-black">
					{/* Light mode image */}
					<Image
						src="/homepage/main_demo.webp"
						alt="header"
						width={1920}
						height={1080}
						className="rounded-[20px] block dark:hidden"
						unoptimized
					/>
					{/* Dark mode image */}
					<Image
						src="/homepage/main_demo.webp"
						alt="header"
						width={1920}
						height={1080}
						className="rounded-[20px] hidden dark:block"
						unoptimized
					/>
				</div>
			</div>
		</div>
	);
}

function GetStartedButton() {
	const isGoogleAuth = AUTH_TYPE === "GOOGLE";

	const handleGoogleLogin = () => {
		trackLoginAttempt("google");
		window.location.href = `${BACKEND_URL}/auth/google/authorize-redirect`;
	};

	if (isGoogleAuth) {
		return (
			<motion.button
				type="button"
				onClick={handleGoogleLogin}
				whileHover="hover"
				whileTap={{ scale: 0.98 }}
				initial="idle"
				className="group relative z-20 flex h-11 w-full cursor-pointer items-center justify-center gap-3 overflow-hidden rounded-xl bg-white px-6 py-2.5 text-sm font-semibold text-neutral-700 shadow-lg ring-1 ring-neutral-200/50 transition-shadow duration-300 hover:shadow-xl sm:w-56 dark:bg-neutral-900 dark:text-neutral-200 dark:ring-neutral-700/50"
				variants={{
					idle: { scale: 1, y: 0 },
					hover: { scale: 1.02, y: -2 },
				}}
			>
				{/* Animated gradient background on hover */}
				<motion.div
					className="absolute inset-0 bg-linear-to-r from-blue-50 via-green-50 to-yellow-50 dark:from-blue-950/30 dark:via-green-950/30 dark:to-yellow-950/30"
					variants={{
						idle: { opacity: 0 },
						hover: { opacity: 1 },
					}}
					transition={{ duration: 0.3 }}
				/>
				{/* Google logo with subtle animation */}
				<motion.div
					className="relative"
					variants={{
						idle: { rotate: 0 },
						hover: { rotate: [0, -8, 8, 0] },
					}}
					transition={{ duration: 0.4, ease: "easeInOut" }}
				>
					<GoogleLogo className="h-5 w-5" />
				</motion.div>
				<span className="relative">Continue with Google</span>
			</motion.button>
		);
	}

	return (
		<motion.div whileHover={{ scale: 1.02, y: -2 }} whileTap={{ scale: 0.98 }}>
			<Link
				href="/login"
				className="group relative z-20 flex h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-xl bg-black px-6 py-2.5 text-sm font-semibold text-white shadow-lg transition-shadow duration-300 hover:shadow-xl sm:w-56 dark:bg-white dark:text-black"
			>
				Get Started
			</Link>
		</motion.div>
	);
}

function ContactSalesButton() {
	return (
		<motion.div whileHover={{ scale: 1.02, y: -2 }} whileTap={{ scale: 0.98 }}>
			<Link
				href="/contact"
				//target="_blank"
				rel="noopener noreferrer"
				className="group relative z-20 flex h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-xl bg-white px-6 py-2.5 text-sm font-semibold text-neutral-700 shadow-lg ring-1 ring-neutral-200/50 transition-shadow duration-300 hover:shadow-xl sm:w-56 dark:bg-neutral-900 dark:text-neutral-200 dark:ring-neutral-700/50"
			>
				Contact Sales
			</Link>
		</motion.div>
	);
}

const BackgroundGrids = () => {
	return (
		<div className="pointer-events-none absolute inset-0 z-0 grid h-full w-full -rotate-45 transform select-none grid-cols-2 gap-10 md:grid-cols-4">
			<div className="relative h-full w-full">
				<GridLineVertical className="left-0" />
				<GridLineVertical className="left-auto right-0" />
			</div>
			<div className="relative h-full w-full">
				<GridLineVertical className="left-0" />
				<GridLineVertical className="left-auto right-0" />
			</div>
			<div className="relative h-full w-full bg-linear-to-b from-transparent via-neutral-100 to-transparent dark:via-neutral-800">
				<GridLineVertical className="left-0" />
				<GridLineVertical className="left-auto right-0" />
			</div>
			<div className="relative h-full w-full">
				<GridLineVertical className="left-0" />
				<GridLineVertical className="left-auto right-0" />
			</div>
		</div>
	);
};

const CollisionMechanism = React.forwardRef<
	HTMLDivElement,
	{
		containerRef: React.RefObject<HTMLDivElement | null>;
		parentRef: React.RefObject<HTMLDivElement | null>;
		beamOptions?: {
			initialX?: number;
			translateX?: number;
			initialY?: number;
			translateY?: number;
			rotate?: number;
			className?: string;
			duration?: number;
			delay?: number;
			repeatDelay?: number;
		};
	}
>(({ parentRef, containerRef, beamOptions = {} }, ref) => {
	const beamRef = useRef<HTMLDivElement>(null);
	const [collision, setCollision] = useState<{
		detected: boolean;
		coordinates: { x: number; y: number } | null;
	}>({ detected: false, coordinates: null });
	const [beamKey, setBeamKey] = useState(0);
	const [cycleCollisionDetected, setCycleCollisionDetected] = useState(false);

	useEffect(() => {
		const checkCollision = () => {
			if (beamRef.current && containerRef.current && parentRef.current && !cycleCollisionDetected) {
				const beamRect = beamRef.current.getBoundingClientRect();
				const containerRect = containerRef.current.getBoundingClientRect();
				const parentRect = parentRef.current.getBoundingClientRect();

				if (beamRect.bottom >= containerRect.top) {
					const relativeX = beamRect.left - parentRect.left + beamRect.width / 2;
					const relativeY = beamRect.bottom - parentRect.top;

					setCollision({
						detected: true,
						coordinates: { x: relativeX, y: relativeY },
					});
					setCycleCollisionDetected(true);
					if (beamRef.current) {
						beamRef.current.style.opacity = "0";
					}
				}
			}
		};

		const animationInterval = setInterval(checkCollision, 100);

		return () => clearInterval(animationInterval);
	}, [cycleCollisionDetected, containerRef]);

	useEffect(() => {
		if (collision.detected && collision.coordinates) {
			setTimeout(() => {
				setCollision({ detected: false, coordinates: null });
				setCycleCollisionDetected(false);
				// Set beam opacity to 0
				if (beamRef.current) {
					beamRef.current.style.opacity = "1";
				}
			}, 2000);

			// Reset the beam animation after a delay
			setTimeout(() => {
				setBeamKey((prevKey) => prevKey + 1);
			}, 2000);
		}
	}, [collision]);

	return (
		<>
			<motion.div
				key={beamKey}
				ref={beamRef}
				animate="animate"
				initial={{
					translateY: beamOptions.initialY || "-200px",
					translateX: beamOptions.initialX || "0px",
					rotate: beamOptions.rotate || -45,
				}}
				variants={{
					animate: {
						translateY: beamOptions.translateY || "800px",
						translateX: beamOptions.translateX || "700px",
						rotate: beamOptions.rotate || -45,
					},
				}}
				transition={{
					duration: beamOptions.duration || 8,
					repeat: Infinity,
					repeatType: "loop",
					ease: "linear",
					delay: beamOptions.delay || 0,
					repeatDelay: beamOptions.repeatDelay || 0,
				}}
				className={cn(
					"absolute left-96 top-20 m-auto h-14 w-px rounded-full bg-linear-to-t from-orange-500 via-yellow-500 to-transparent will-change-transform",
					beamOptions.className
				)}
			/>
			<AnimatePresence>
				{collision.detected && collision.coordinates && (
					<Explosion
						key={`${collision.coordinates.x}-${collision.coordinates.y}`}
						className=""
						style={{
							left: `${collision.coordinates.x + 20}px`,
							top: `${collision.coordinates.y}px`,
							transform: "translate(-50%, -50%)",
						}}
					/>
				)}
			</AnimatePresence>
		</>
	);
});

CollisionMechanism.displayName = "CollisionMechanism";

const Explosion = ({ ...props }: React.HTMLProps<HTMLDivElement>) => {
	const spans = Array.from({ length: 20 }, (_, index) => ({
		id: index,
		initialX: 0,
		initialY: 0,
		directionX: Math.floor(Math.random() * 80 - 40),
		directionY: Math.floor(Math.random() * -50 - 10),
	}));

	return (
		<div {...props} className={cn("absolute z-50 h-2 w-2", props.className)}>
			<motion.div
				initial={{ opacity: 0 }}
				animate={{ opacity: [0, 1, 0] }}
				exit={{ opacity: 0 }}
				transition={{ duration: 1, ease: "easeOut" }}
				className="absolute -inset-x-10 top-0 m-auto h-[4px] w-10 rounded-full bg-linear-to-r from-transparent via-orange-500 to-transparent blur-sm"
			></motion.div>
			{spans.map((span) => (
				<motion.span
					key={span.id}
					initial={{ x: span.initialX, y: span.initialY, opacity: 1 }}
					animate={{ x: span.directionX, y: span.directionY, opacity: 0 }}
					transition={{ duration: Math.random() * 1.5 + 0.5, ease: "easeOut" }}
					className="absolute h-1 w-1 rounded-full bg-linear-to-b from-orange-500 to-yellow-500"
				/>
			))}
		</div>
	);
};

const GridLineVertical = ({ className, offset }: { className?: string; offset?: string }) => {
	return (
		<div
			style={
				{
					"--background": "#ffffff",
					"--color": "rgba(0, 0, 0, 0.2)",
					"--height": "5px",
					"--width": "1px",
					"--fade-stop": "90%",
					"--offset": offset || "150px", //-100px if you want to keep the line inside
					"--color-dark": "rgba(255, 255, 255, 0.3)",
					maskComposite: "exclude",
				} as React.CSSProperties
			}
			className={cn(
				"absolute top-[calc(var(--offset)/2*-1)] h-[calc(100%+var(--offset))] w-(--width)",
				"bg-[linear-gradient(to_bottom,var(--color),var(--color)_50%,transparent_0,transparent)]",
				"bg-size-[var(--width)_var(--height)]",
				"[mask:linear-gradient(to_top,var(--background)_var(--fade-stop),transparent),linear-gradient(to_bottom,var(--background)_var(--fade-stop),transparent),linear-gradient(black,black)]",
				"mask-exclude",
				"z-30",
				"dark:bg-[linear-gradient(to_bottom,var(--color-dark),var(--color-dark)_50%,transparent_0,transparent)]",
				className
			)}
		></div>
	);
};
