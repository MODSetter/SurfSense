"use client";

import { type ReactNode, useEffect, useRef } from "react";

/**
 * Marks its subtree `data-offscreen` while it is out of view, which pauses any
 * `.ss-home-marquee` inside it (see `home.css`). An attribute, not state, so
 * scrolling past never re-renders the chips.
 */
export function PauseOffscreen({
	className,
	children,
}: {
	className?: string;
	children: ReactNode;
}) {
	const ref = useRef<HTMLDivElement>(null);

	useEffect(() => {
		const node = ref.current;
		if (!node) return;
		const observer = new IntersectionObserver(([entry]) => {
			node.toggleAttribute("data-offscreen", !entry.isIntersecting);
		});
		observer.observe(node);
		return () => observer.disconnect();
	}, []);

	return (
		<div ref={ref} data-offscreen="" className={className}>
			{children}
		</div>
	);
}
