"use client";

import Lenis from "lenis";
import "lenis/dist/lenis.css";
import { useEffect } from "react";

/**
 * Lenis smooth scrolling for the landing page only; mounting it here rather than
 * in the (home) layout keeps the other marketing routes on native scroll.
 */
export function HomeSmoothScroll() {
	useEffect(() => {
		if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

		const lenis = new Lenis({ autoRaf: true, anchors: true });
		return () => lenis.destroy();
	}, []);

	return null;
}
