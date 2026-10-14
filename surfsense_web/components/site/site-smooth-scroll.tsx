"use client";

import Lenis from "lenis";
import "lenis/dist/lenis.css";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

/**
 * Lenis smooth scrolling for every marketing route, mounted once in the shell so
 * it survives navigations. Off for visitors who ask for reduced motion.
 */
export function SiteSmoothScroll() {
	const pathname = usePathname();
	const lenisRef = useRef<Lenis | null>(null);
	const firstPath = useRef(true);

	useEffect(() => {
		if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

		const lenis = new Lenis({ autoRaf: true, anchors: true });
		lenisRef.current = lenis;
		return () => {
			lenis.destroy();
			lenisRef.current = null;
		};
	}, []);

	// A link clicked mid-glide would carry the old page's momentum onto the new
	// one. Once Next has placed the new page, settle Lenis where it actually is.
	useEffect(() => {
		if (firstPath.current) {
			firstPath.current = false;
			return;
		}
		const frame = requestAnimationFrame(() => {
			lenisRef.current?.scrollTo(window.scrollY, { immediate: true, force: true });
		});
		return () => cancelAnimationFrame(frame);
	}, [pathname]);

	return null;
}
