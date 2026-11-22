"use client";

import type React from "react";
import { useCallback, useEffect, useRef, useState } from "react";

/**
 * A macOS-style dock whose icons magnify around the cursor, from 21st.dev
 * (dhmnpunit/mac-os-dock). Adapted for this codebase: no GSAP (it is not a
 * dependency), clicks are optional so the dock can be decorative, the sizes
 * can be fixed by props for small previews, and reduced motion turns the
 * magnification off.
 */

export interface DockApp {
	id: string;
	name: string;
	icon: string;
}

interface MacOSDockProps {
	apps: DockApp[];
	onAppClick?: (appId: string) => void;
	openApps?: string[];
	className?: string;
	/** Fixed sizes; without them the dock sizes itself to the viewport. */
	iconSize?: number;
	maxScale?: number;
	effectWidth?: number;
	/** `light` takes the site palette, to sit among the other card previews. */
	tone?: "dark" | "light";
}

type DockConfig = { baseIconSize: number; maxScale: number; effectWidth: number };

function responsiveConfig(): DockConfig {
	if (typeof window === "undefined") {
		return { baseIconSize: 64, maxScale: 1.6, effectWidth: 240 };
	}
	const smallerDimension = Math.min(window.innerWidth, window.innerHeight);
	if (smallerDimension < 480) {
		return {
			baseIconSize: Math.max(40, smallerDimension * 0.08),
			maxScale: 1.4,
			effectWidth: smallerDimension * 0.4,
		};
	}
	if (smallerDimension < 768) {
		return {
			baseIconSize: Math.max(48, smallerDimension * 0.07),
			maxScale: 1.5,
			effectWidth: smallerDimension * 0.35,
		};
	}
	if (smallerDimension < 1024) {
		return {
			baseIconSize: Math.max(56, smallerDimension * 0.06),
			maxScale: 1.6,
			effectWidth: smallerDimension * 0.3,
		};
	}
	return {
		baseIconSize: Math.max(64, Math.min(80, smallerDimension * 0.05)),
		maxScale: 1.8,
		effectWidth: 300,
	};
}

const MIN_SCALE = 1;

/** Each icon's centre along the tray, laid out left to right at the given scales. */
function layoutCenters(scales: number[], iconSize: number, spacing: number): number[] {
	let currentX = 0;
	return scales.map((scale) => {
		const scaledWidth = iconSize * scale;
		const centerX = currentX + scaledWidth / 2;
		currentX += scaledWidth + spacing;
		return centerX;
	});
}

export function MacOSDock({
	apps,
	onAppClick,
	openApps = [],
	className = "",
	iconSize,
	maxScale: maxScaleProp,
	effectWidth: effectWidthProp,
	tone = "dark",
}: MacOSDockProps) {
	const fixed = iconSize !== undefined;
	const [config, setConfig] = useState<DockConfig>(() =>
		fixed
			? {
					baseIconSize: iconSize,
					maxScale: maxScaleProp ?? 1.6,
					effectWidth: effectWidthProp ?? iconSize * 4,
				}
			: responsiveConfig()
	);
	const { baseIconSize, maxScale, effectWidth } = config;
	const baseSpacing = Math.max(4, baseIconSize * 0.08);

	const [mouseX, setMouseX] = useState<number | null>(null);
	const [currentScales, setCurrentScales] = useState<number[]>(() => apps.map(() => MIN_SCALE));
	// Laid out from the start, not in an effect: the server-rendered HTML has to
	// place every icon, or they all stack at the left edge until hydration.
	const [currentPositions, setCurrentPositions] = useState<number[]>(() =>
		layoutCenters(
			apps.map(() => MIN_SCALE),
			baseIconSize,
			baseSpacing
		)
	);
	const [reducedMotion, setReducedMotion] = useState(false);
	const dockRef = useRef<HTMLDivElement>(null);
	const iconRefs = useRef<(HTMLElement | null)[]>([]);
	const animationFrameRef = useRef<number | undefined>(undefined);
	const lastMouseMoveTime = useRef(0);

	useEffect(() => {
		const query = window.matchMedia("(prefers-reduced-motion: reduce)");
		setReducedMotion(query.matches);
		const onChange = () => setReducedMotion(query.matches);
		query.addEventListener("change", onChange);
		return () => query.removeEventListener("change", onChange);
	}, []);

	useEffect(() => {
		if (fixed) return;
		const handleResize = () => setConfig(responsiveConfig());
		window.addEventListener("resize", handleResize);
		return () => window.removeEventListener("resize", handleResize);
	}, [fixed]);

	// The macOS falloff: a raised cosine across `effectWidth`, centred on the cursor.
	const calculateTargetMagnification = useCallback(
		(mousePosition: number | null) => {
			if (mousePosition === null || reducedMotion) return apps.map(() => MIN_SCALE);
			return apps.map((_, index) => {
				const center = index * (baseIconSize + baseSpacing) + baseIconSize / 2;
				const minX = mousePosition - effectWidth / 2;
				const maxX = mousePosition + effectWidth / 2;
				if (center < minX || center > maxX) return MIN_SCALE;
				const theta = ((center - minX) / effectWidth) * 2 * Math.PI;
				const scaleFactor = (1 - Math.cos(Math.min(Math.max(theta, 0), 2 * Math.PI))) / 2;
				return MIN_SCALE + scaleFactor * (maxScale - MIN_SCALE);
			});
		},
		[apps, baseIconSize, baseSpacing, effectWidth, maxScale, reducedMotion]
	);

	const calculatePositions = useCallback(
		(scales: number[]) => layoutCenters(scales, baseIconSize, baseSpacing),
		[baseIconSize, baseSpacing]
	);

	useEffect(() => {
		const initialScales = apps.map(() => MIN_SCALE);
		setCurrentScales(initialScales);
		setCurrentPositions(calculatePositions(initialScales));
	}, [apps, calculatePositions]);

	const animateToTarget = useCallback(() => {
		const targetScales = calculateTargetMagnification(mouseX);
		const targetPositions = calculatePositions(targetScales);
		const lerpFactor = mouseX !== null ? 0.2 : 0.12;

		setCurrentScales((prev) =>
			prev.map((scale, index) => scale + (targetScales[index] - scale) * lerpFactor)
		);
		setCurrentPositions((prev) =>
			prev.map((pos, index) => pos + (targetPositions[index] - pos) * lerpFactor)
		);

		const settling =
			currentScales.some((scale, index) => Math.abs(scale - targetScales[index]) > 0.002) ||
			currentPositions.some((pos, index) => Math.abs(pos - targetPositions[index]) > 0.1);
		if (settling || mouseX !== null) {
			animationFrameRef.current = requestAnimationFrame(animateToTarget);
		}
	}, [mouseX, calculateTargetMagnification, calculatePositions, currentScales, currentPositions]);

	useEffect(() => {
		if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
		animationFrameRef.current = requestAnimationFrame(animateToTarget);
		return () => {
			if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
		};
	}, [animateToTarget]);

	const padding = Math.max(8, baseIconSize * 0.12);

	// Throttled to one update a frame.
	const handleMouseMove = useCallback(
		(event: React.MouseEvent) => {
			const now = performance.now();
			if (now - lastMouseMoveTime.current < 16) return;
			lastMouseMoveTime.current = now;
			if (dockRef.current) {
				const rect = dockRef.current.getBoundingClientRect();
				setMouseX(event.clientX - rect.left - padding);
			}
		},
		[padding]
	);

	const handleAppClick = (appId: string, index: number) => {
		const element = iconRefs.current[index];
		if (element && !reducedMotion) {
			element.style.transition = "transform 0.2s ease-out";
			element.style.transform = `translateY(${Math.max(-8, -baseIconSize * 0.15)}px)`;
			setTimeout(() => {
				element.style.transform = "translateY(0px)";
			}, 200);
		}
		onAppClick?.(appId);
	};

	const contentWidth =
		currentPositions.length > 0
			? Math.max(
					...currentPositions.map((pos, index) => pos + (baseIconSize * currentScales[index]) / 2)
				)
			: apps.length * (baseIconSize + baseSpacing) - baseSpacing;

	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: the pointer only drives the magnification, a visual effect; anything clickable is a real button inside.
		<div
			ref={dockRef}
			role="presentation"
			className={`backdrop-blur-md ${className}`}
			style={{
				width: `${contentWidth + padding * 2}px`,
				background: tone === "light" ? "var(--card)" : "rgba(45, 45, 45, 0.75)",
				borderRadius: `${Math.max(12, baseIconSize * 0.4)}px`,
				border:
					tone === "light" ? "1px solid var(--border)" : "1px solid rgba(255, 255, 255, 0.15)",
				boxShadow:
					tone === "light"
						? `0 ${Math.max(4, baseIconSize * 0.1)}px ${Math.max(16, baseIconSize * 0.4)}px -${Math.max(6, baseIconSize * 0.15)}px rgba(0, 0, 0, 0.18), 0 1px 2px rgba(0, 0, 0, 0.05), inset 0 1px 0 rgba(255, 255, 255, 0.9)`
						: `
					0 ${Math.max(4, baseIconSize * 0.1)}px ${Math.max(16, baseIconSize * 0.4)}px rgba(0, 0, 0, 0.4),
					0 ${Math.max(2, baseIconSize * 0.05)}px ${Math.max(8, baseIconSize * 0.2)}px rgba(0, 0, 0, 0.3),
					inset 0 1px 0 rgba(255, 255, 255, 0.15),
					inset 0 -1px 0 rgba(0, 0, 0, 0.2)
				`,
				padding: `${padding}px`,
			}}
			onMouseMove={handleMouseMove}
			onMouseLeave={() => setMouseX(null)}
		>
			<div className="relative" style={{ height: `${baseIconSize}px`, width: "100%" }}>
				{apps.map((app, index) => {
					const scale = currentScales[index] ?? MIN_SCALE;
					const position = currentPositions[index] || 0;
					const scaledSize = baseIconSize * scale;
					const style: React.CSSProperties = {
						left: `${position - scaledSize / 2}px`,
						bottom: "0px",
						width: `${scaledSize}px`,
						height: `${scaledSize}px`,
						transformOrigin: "bottom center",
						zIndex: Math.round(scale * 10),
					};
					const content = (
						<>
							{/* biome-ignore lint/performance/noImgElement: icons resize every frame of the magnification, which `next/image` would refetch at each new size. */}
							<img
								src={app.icon}
								alt={onAppClick ? app.name : ""}
								width={scaledSize}
								height={scaledSize}
								draggable={false}
								className="object-contain select-none"
								style={{
									filter: `drop-shadow(0 ${scale > 1.2 ? Math.max(2, baseIconSize * 0.05) : Math.max(1, baseIconSize * 0.03)}px ${scale > 1.2 ? Math.max(4, baseIconSize * 0.1) : Math.max(2, baseIconSize * 0.06)}px rgba(0,0,0,${0.2 + (scale - 1) * 0.15}))`,
								}}
							/>
							{openApps.includes(app.id) && (
								<span
									className="absolute"
									style={{
										bottom: `${Math.max(-2, -baseIconSize * 0.05)}px`,
										left: "50%",
										transform: "translateX(-50%)",
										width: `${Math.max(3, baseIconSize * 0.06)}px`,
										height: `${Math.max(3, baseIconSize * 0.06)}px`,
										borderRadius: "50%",
										backgroundColor:
											tone === "light" ? "var(--foreground)" : "rgba(255, 255, 255, 0.8)",
										boxShadow: "0 0 4px rgba(0, 0, 0, 0.3)",
									}}
								/>
							)}
						</>
					);

					return onAppClick ? (
						<button
							key={app.id}
							type="button"
							ref={(el) => {
								iconRefs.current[index] = el;
							}}
							title={app.name}
							onClick={() => handleAppClick(app.id, index)}
							className="absolute flex cursor-pointer flex-col items-center justify-end"
							style={style}
						>
							{content}
						</button>
					) : (
						<div
							key={app.id}
							ref={(el) => {
								iconRefs.current[index] = el;
							}}
							className="absolute flex flex-col items-center justify-end"
							style={style}
						>
							{content}
						</div>
					);
				})}
			</div>
		</div>
	);
}

export default MacOSDock;
