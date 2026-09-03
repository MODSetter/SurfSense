"use client";

import type { CSSProperties, ReactNode } from "react";
import { useEffect, useLayoutEffect, useRef } from "react";
import type { RightPanelTab } from "@/atoms/layout/right-panel.atom";
import { cn } from "@/lib/utils";

const RIGHT_PANEL_LAYOUT: Record<RightPanelTab, { ratio: string; maxWidth: string }> = {
	sources: { ratio: "40%", maxWidth: "420px" },
	artifacts: { ratio: "40%", maxWidth: "420px" },
	citation: { ratio: "45%", maxWidth: "560px" },
	document: { ratio: "50%", maxWidth: "640px" },
	artifact: { ratio: "50%", maxWidth: "640px" },
	editor: { ratio: "50%", maxWidth: "640px" },
	"hitl-edit": { ratio: "50%", maxWidth: "640px" },
};

export function hasHorizontalOverflow({
	clientWidth,
	scrollWidth,
}: Pick<HTMLElement, "clientWidth" | "scrollWidth">): boolean {
	return scrollWidth > clientWidth + 1;
}

export function didHorizontalOverflowBegin(
	wasOverflowing: boolean,
	dimensions: Pick<HTMLElement, "clientWidth" | "scrollWidth">
): boolean {
	return !wasOverflowing && hasHorizontalOverflow(dimensions);
}

export function shouldAutoCollapseSidebar(
	wasOverflowing: boolean,
	suppressedByManualExpansion: boolean,
	dimensions: Pick<HTMLElement, "clientWidth" | "scrollWidth">
): boolean {
	return !suppressedByManualExpansion && didHorizontalOverflowBegin(wasOverflowing, dimensions);
}

interface WorkspaceSplitProps {
	primary: ReactNode;
	secondary: ReactNode;
	secondaryTab: RightPanelTab;
	secondaryVisible: boolean;
	sidebarCollapsed: boolean;
	overlay?: ReactNode;
	onPrimaryOverflow?: () => void;
	className?: string;
}

export function WorkspaceSplit({
	primary,
	secondary,
	secondaryTab,
	secondaryVisible,
	sidebarCollapsed,
	overlay,
	onPrimaryOverflow,
	className,
}: WorkspaceSplitProps) {
	const primaryRef = useRef<HTMLDivElement>(null);
	const wasOverflowingRef = useRef(false);
	const previousSidebarCollapsedRef = useRef(sidebarCollapsed);
	const suppressAutoCollapseRef = useRef(false);
	const layout = RIGHT_PANEL_LAYOUT[secondaryTab];
	const secondaryTrack = secondaryVisible
		? `minmax(0, min(${layout.ratio}, ${layout.maxWidth}))`
		: "0px";

	useLayoutEffect(() => {
		if (previousSidebarCollapsedRef.current && !sidebarCollapsed) {
			suppressAutoCollapseRef.current = true;
		}
		previousSidebarCollapsedRef.current = sidebarCollapsed;
	}, [sidebarCollapsed]);

	useEffect(() => {
		const primaryPane = primaryRef.current;
		if (!primaryPane || !onPrimaryOverflow) return;

		let frame = 0;
		const update = () => {
			cancelAnimationFrame(frame);
			frame = requestAnimationFrame(() => {
				const isOverflowing = hasHorizontalOverflow(primaryPane);
				if (
					shouldAutoCollapseSidebar(
						wasOverflowingRef.current,
						suppressAutoCollapseRef.current,
						primaryPane
					)
				) {
					onPrimaryOverflow();
				}
				if (!isOverflowing) suppressAutoCollapseRef.current = false;
				wasOverflowingRef.current = isOverflowing;
			});
		};
		const observer = new ResizeObserver(update);
		observer.observe(primaryPane);
		update();

		return () => {
			cancelAnimationFrame(frame);
			observer.disconnect();
		};
	}, [onPrimaryOverflow]);

	return (
		<div
			data-workspace-split
			data-secondary-tab={secondaryTab}
			data-secondary-visible={secondaryVisible}
			className={cn("relative grid h-full min-h-0 min-w-0 w-full overflow-hidden", className)}
			style={
				{
					gridTemplateColumns: `minmax(0, 1fr) ${secondaryTrack}`,
				} satisfies CSSProperties
			}
		>
			<div
				ref={primaryRef}
				data-primary-pane
				className="relative flex h-full min-h-0 min-w-0 w-full overflow-hidden"
			>
				{primary}
			</div>
			<div
				data-secondary-pane
				aria-hidden={!secondaryVisible}
				className="relative flex h-full min-h-0 min-w-0 w-full overflow-hidden"
			>
				{secondary}
			</div>
			{overlay}
		</div>
	);
}
