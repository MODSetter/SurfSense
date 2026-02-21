"use client";

import { AnimatePresence, motion } from "motion/react";
import { useMediaQuery } from "@/hooks/use-media-query";
import { cn } from "@/lib/utils";
import { useSidebarContextSafe } from "../../hooks";

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

	return (
		<AnimatePresence>
			{open && (
				<>
					{/* Click-away layer - covers the full container including the sidebar */}
					<motion.div
						initial={{ opacity: 0 }}
						animate={{ opacity: 1 }}
						exit={{ opacity: 0 }}
						transition={{ duration: 0.15 }}
						className="absolute inset-0 z-[5]"
						onClick={() => onOpenChange(false)}
						aria-hidden="true"
					/>

					{/* Clip container - positioned at sidebar edge with overflow hidden */}
					<div
						style={{
							left: isMobile ? 0 : sidebarWidth,
							width: isMobile ? "100%" : width,
						}}
						className={cn("absolute z-10 overflow-hidden pointer-events-none", "inset-y-0")}
					>
						<motion.div
							initial={{ x: "-100%" }}
							animate={{ x: 0 }}
							exit={{ x: "-100%" }}
							transition={{ type: "tween", duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
							className={cn(
								"h-full w-full bg-background flex flex-col pointer-events-auto select-none",
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
