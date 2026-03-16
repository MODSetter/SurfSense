"use client";

import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect } from "react";
import { useMediaQuery } from "@/hooks/use-media-query";

export const SLIDEOUT_PANEL_OPENED_EVENT = "slideout-panel-opened";

interface SidebarSlideOutPanelProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	ariaLabel: string;
	width?: number;
	children: React.ReactNode;
}

/**
 * Reusable slide-out panel that extends from the sidebar.
 *
 * Desktop: absolutely positioned at the sidebar's right edge, overlaying the main
 * content with a blur backdrop. Does not push/shrink the main content.
 *
 * Mobile: full-width absolute overlay (unchanged).
 */
export function SidebarSlideOutPanel({
	open,
	onOpenChange,
	ariaLabel,
	width = 360,
	children,
}: SidebarSlideOutPanelProps) {
	const isMobile = !useMediaQuery("(min-width: 640px)");

	useEffect(() => {
		if (open) {
			window.dispatchEvent(new Event(SLIDEOUT_PANEL_OPENED_EVENT));
		}
	}, [open]);

	const handleEscape = useCallback(
		(e: KeyboardEvent) => {
			if (e.key === "Escape") onOpenChange(false);
		},
		[onOpenChange]
	);

	useEffect(() => {
		if (!open) return;
		document.addEventListener("keydown", handleEscape);
		return () => document.removeEventListener("keydown", handleEscape);
	}, [open, handleEscape]);

	if (isMobile) {
		return (
			<AnimatePresence>
				{open && (
					<div className="absolute left-0 inset-y-0 z-30 w-full overflow-hidden pointer-events-none">
						<motion.div
							initial={{ x: "-100%" }}
							animate={{ x: 0 }}
							exit={{ x: "-100%" }}
							transition={{ type: "tween", duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
							className="h-full w-full bg-sidebar text-sidebar-foreground flex flex-col pointer-events-auto select-none"
							role="dialog"
							aria-modal="true"
							aria-label={ariaLabel}
						>
							{children}
						</motion.div>
					</div>
				)}
			</AnimatePresence>
		);
	}

	return (
		<AnimatePresence initial={false}>
			{open && (
				<>
					{/* Blur backdrop covering the main content area (right of sidebar) */}
					<motion.div
						initial={{ opacity: 0 }}
						animate={{ opacity: 1 }}
						exit={{ opacity: 0 }}
						transition={{ duration: 0.15 }}
						className="absolute z-10 bg-black/30 backdrop-blur-sm rounded-xl"
						style={{ top: -9, bottom: -9, left: "calc(100% + 1px)", width: "200vw" }}
						onClick={() => onOpenChange(false)}
						aria-hidden="true"
					/>

					{/* Panel extending from sidebar's right edge, flush with the wrapper border */}
					<motion.div
						initial={{ width: 0 }}
						animate={{ width }}
						exit={{ width: 0 }}
						transition={{ type: "tween", duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
						className="absolute z-20 overflow-hidden"
						style={{ left: "100%", top: -1, bottom: -1 }}
					>
						<div
							style={{ width }}
							className="h-full bg-sidebar text-sidebar-foreground flex flex-col select-none border rounded-r-xl shadow-xl"
							role="dialog"
							aria-label={ariaLabel}
						>
							{children}
						</div>
					</motion.div>
				</>
			)}
		</AnimatePresence>
	);
}
