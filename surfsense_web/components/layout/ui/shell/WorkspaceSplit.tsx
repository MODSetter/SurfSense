"use client";

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";
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

/** Width tween from the pre-split RightPanel (`PANEL_SLIDE_TRANSITION.width`). */
const PANEL_WIDTH_TRANSITION = { duration: 0.24, ease: [0.4, 0, 0.2, 1] } as const;

function paneInnerSize(layout: { ratio: string; maxWidth: string }) {
	return `min(${layout.ratio.replace("%", "cqw")}, ${layout.maxWidth})`;
}

export function hasHorizontalOverflow({
	clientWidth,
	scrollWidth,
}: Pick<HTMLElement, "clientWidth" | "scrollWidth">): boolean {
	return scrollWidth > clientWidth + 1;
}

export function shouldAutoCollapseSidebar(
	wasOverflowing: boolean,
	isOverflowing: boolean
): boolean {
	return !wasOverflowing && isOverflowing;
}

interface WorkspaceSplitProps {
	primary: ReactNode;
	secondary: ReactNode;
	secondaryTab: RightPanelTab;
	secondaryVisible: boolean;
	overlay?: ReactNode;
	className?: string;
}

export function WorkspaceSplit({
	primary,
	secondary,
	secondaryTab,
	secondaryVisible,
	overlay,
	className,
}: WorkspaceSplitProps) {
	const reduceMotion = useReducedMotion();
	const layout = RIGHT_PANEL_LAYOUT[secondaryTab];
	const innerSize = paneInnerSize(layout);

	return (
		<div
			data-workspace-split
			data-secondary-tab={secondaryTab}
			data-secondary-visible={secondaryVisible}
			className={cn(
				"@container relative flex h-full min-h-0 min-w-0 w-full overflow-hidden",
				className
			)}
		>
			<div
				data-primary-pane
				className="relative flex h-full min-h-0 min-w-0 flex-1 overflow-hidden"
			>
				{primary}
			</div>
			<motion.div
				data-secondary-pane
				aria-hidden={!secondaryVisible}
				initial={false}
				animate={{
					width: secondaryVisible ? layout.ratio : "0%",
					maxWidth: secondaryVisible ? layout.maxWidth : "0px",
				}}
				transition={reduceMotion ? { duration: 0 } : PANEL_WIDTH_TRANSITION}
				className="relative h-full min-h-0 min-w-0 shrink-0 overflow-hidden"
			>
				<div className="flex h-full min-h-0 shrink-0 flex-col" style={{ width: innerSize }}>
					{secondary}
				</div>
			</motion.div>
			{overlay}
		</div>
	);
}
