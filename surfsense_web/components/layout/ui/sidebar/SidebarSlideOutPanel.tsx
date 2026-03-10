"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect } from "react";
import { useMediaQuery } from "@/hooks/use-media-query";
import { cn } from "@/lib/utils";
import { useSidebarContextSafe } from "../../hooks";

export const SLIDEOUT_PANEL_OPENED_EVENT = "slideout-panel-opened";

const SIDEBAR_COLLAPSED_WIDTH = 60;

interface SidebarSlideOutPanelProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	ariaLabel: string;
	width?: number;
	children: React.ReactNode;
}

/**
 * Reusable slide-out panel that appears from the right edge of the sidebar.
 * Used by InboxSidebar (floating mode), AllSharedChatsSidebar, and AllPrivateChatsSidebar.
 *
 * Must be rendered inside a positioned container (the LayoutShell's relative flex container)
 * and within the SidebarProvider context.
 */
export function SidebarSlideOutPanel({
	open,
	onOpenChange,
	ariaLabel,
	width = 360,
	children,
}: SidebarSlideOutPanelProps) {
	const isMobile = !useMediaQuery("(min-width: 640px)");
	const sidebarContext = useSidebarContextSafe();
	const isCollapsed = sidebarContext?.isCollapsed ?? false;
	const sidebarWidth = isCollapsed
		? SIDEBAR_COLLAPSED_WIDTH
		: (sidebarContext?.sidebarWidth ?? 240);

	useEffect(() => {
		if (open) {
			window.dispatchEvent(new Event(SLIDEOUT_PANEL_OPENED_EVENT));
		}
	}, [open]);

	return (
		<AnimatePresence>
			{open && (
				<>
					{/* Backdrop overlay with blur — only covers the main content area (right of sidebar) */}
					<motion.div
						initial={{ opacity: 0 }}
						animate={{ opacity: 1 }}
						exit={{ opacity: 0 }}
						transition={{ duration: 0.15 }}
						style={{ left: isMobile ? 0 : sidebarWidth }}
						className="absolute inset-y-0 right-0 z-20 bg-black/30 backdrop-blur-sm"
						onClick={() => onOpenChange(false)}
						aria-hidden="true"
					/>

					{/* Clip container - positioned at sidebar edge with overflow hidden */}
					<div
						style={{
							left: isMobile ? 0 : sidebarWidth,
							width: isMobile ? "100%" : width,
						}}
						className={cn("absolute z-30 overflow-hidden pointer-events-none", "inset-y-0")}
					>
						<motion.div
							initial={{ x: "-100%" }}
							animate={{ x: 0 }}
							exit={{ x: "-100%" }}
							transition={{ type: "tween", duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
							className={cn(
								"h-full w-full bg-sidebar text-sidebar-foreground flex flex-col pointer-events-auto select-none",
								"sm:border-r sm:shadow-xl"
							)}
							role="dialog"
							aria-modal="true"
							aria-label={ariaLabel}
						>
							{children}
						</motion.div>
					</div>
				</>
			)}
		</AnimatePresence>
	);
}
