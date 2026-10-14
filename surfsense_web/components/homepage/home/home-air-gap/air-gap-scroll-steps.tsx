"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";
import type { AirGapNode } from "@/components/homepage/home/home-content";

const STEPS: AirGapNode[] = ["index", "model", "outputs"];

/**
 * Drives the diagram from scroll: `data-active` names the current claim.
 *
 * On lg the frame pins inside a 300vh track and the step follows progress
 * through it: two screens of scroll, a third each. Below lg the frame is
 * taller than a phone screen, so it scrolls normally and a claim becomes
 * active as it crosses a line 60% down the viewport.
 */
export function AirGapScrollSteps({
	className,
	children,
}: {
	className?: string;
	children: ReactNode;
}) {
	const trackRef = useRef<HTMLDivElement>(null);
	const [active, setActive] = useState<AirGapNode>("index");

	useEffect(() => {
		const track = trackRef.current;
		if (!track) {
			return;
		}
		const wide = window.matchMedia("(min-width: 1024px)");

		const followProgress = () => {
			let frame = 0;
			const update = () => {
				frame = 0;
				// Progress runs exactly while the figure is pinned: from its sticky
				// `top` until it reaches the end of the track.
				const figure = track.firstElementChild as HTMLElement | null;
				if (!figure) {
					return;
				}
				const rect = track.getBoundingClientRect();
				const pinTop = Number.parseFloat(getComputedStyle(figure).top) || 0;
				const travel = rect.height - figure.offsetHeight;
				const progress =
					travel > 0 ? Math.min(Math.max((pinTop - rect.top) / travel, 0), 0.999) : 0;
				setActive(STEPS[Math.floor(progress * STEPS.length)] ?? "index");
			};
			const onScroll = () => {
				if (!frame) {
					frame = requestAnimationFrame(update);
				}
			};
			update();
			window.addEventListener("scroll", onScroll, { passive: true });
			window.addEventListener("resize", onScroll);
			return () => {
				cancelAnimationFrame(frame);
				window.removeEventListener("scroll", onScroll);
				window.removeEventListener("resize", onScroll);
			};
		};

		const followClaims = () => {
			const steps = new IntersectionObserver(
				(entries) => {
					for (const entry of entries) {
						const claim = (entry.target as HTMLElement).dataset.claim as AirGapNode | undefined;
						if (entry.isIntersecting && claim) {
							setActive(claim);
						}
					}
				},
				{ rootMargin: "-60% 0px -35% 0px" }
			);
			for (const claim of track.querySelectorAll("[data-claim]")) {
				steps.observe(claim);
			}
			return () => steps.disconnect();
		};

		let stop = wide.matches ? followProgress() : followClaims();
		const onBreakpoint = () => {
			stop();
			stop = wide.matches ? followProgress() : followClaims();
		};
		wide.addEventListener("change", onBreakpoint);
		return () => {
			wide.removeEventListener("change", onBreakpoint);
			stop();
		};
	}, []);

	return (
		<div ref={trackRef} className="ss-airgap-root relative lg:h-[300vh]" data-active={active}>
			<div className={className}>{children}</div>
		</div>
	);
}
