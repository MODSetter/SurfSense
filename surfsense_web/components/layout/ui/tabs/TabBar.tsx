"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { Plus, X } from "lucide-react";
import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import {
	activeTabIdAtom,
	closeTabAtom,
	switchTabAtom,
	type Tab,
	tabsAtom,
} from "@/atoms/tabs/tabs.atom";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface TabBarProps {
	onTabSwitch?: (tab: Tab) => void;
	onNewChat?: () => void;
	leftActions?: React.ReactNode;
	rightActions?: React.ReactNode;
	className?: string;
}

// Pure scroll-target calculation for the tab list.
// - When the list shrinks (a tab was closed), do not move the scroll.
// - When the list overflows after growing, snap to the right edge so the new tab is visible.
function nextTabListScrollLeft(input: {
	prevScrollWidth: number;
	scrollWidth: number;
	clientWidth: number;
}) {
	if (input.scrollWidth <= input.prevScrollWidth) return;
	if (input.scrollWidth <= input.clientWidth) return;
	return input.scrollWidth - input.clientWidth;
}

export function TabBar({
	onTabSwitch,
	onNewChat,
	leftActions,
	rightActions,
	className,
}: TabBarProps) {
	const tabs = useAtomValue(tabsAtom);
	const activeTabId = useAtomValue(activeTabIdAtom);
	const switchTab = useSetAtom(switchTabAtom);
	const closeTab = useSetAtom(closeTabAtom);
	const scrollRef = useRef<HTMLDivElement>(null);
	const [hoveredTabIndex, setHoveredTabIndex] = useState<number | null>(null);
	const activeTabIndex = tabs.findIndex((tab) => tab.id === activeTabId);

	const shouldHideSeparator = useCallback(
		(separatorIndex: number) => {
			// separatorIndex sits between tabs[separatorIndex - 1] and tabs[separatorIndex].
			return (
				hoveredTabIndex === separatorIndex - 1 ||
				hoveredTabIndex === separatorIndex ||
				activeTabIndex === separatorIndex - 1 ||
				activeTabIndex === separatorIndex
			);
		},
		[hoveredTabIndex, activeTabIndex]
	);

	const handleTabClick = useCallback(
		(tab: Tab) => {
			if (tab.id === activeTabId) return;
			switchTab(tab.id);
			onTabSwitch?.(tab);
		},
		[activeTabId, switchTab, onTabSwitch]
	);

	const handleTabClose = useCallback(
		(e: React.MouseEvent, tabId: string) => {
			e.stopPropagation();
			const fallback = closeTab(tabId);
			if (fallback) {
				onTabSwitch?.(fallback);
			}
		},
		[closeTab, onTabSwitch]
	);

	// React to tab list growth via a MutationObserver so the scroll catches the
	// moment a new tab is added to the DOM, not after activation lands.
	// Also remaps vertical wheel motion to horizontal scroll.
	useEffect(() => {
		const el = scrollRef.current;
		if (!el) return;

		let prevScrollWidth = el.scrollWidth;
		let frame: number | undefined;

		const update = () => {
			const left = nextTabListScrollLeft({
				prevScrollWidth,
				scrollWidth: el.scrollWidth,
				clientWidth: el.clientWidth,
			});
			if (left !== undefined) {
				el.scrollTo({ left, behavior: "smooth" });
			}
			prevScrollWidth = el.scrollWidth;
		};

		const schedule = () => {
			if (frame !== undefined) cancelAnimationFrame(frame);
			frame = requestAnimationFrame(() => {
				frame = undefined;
				update();
			});
		};

		const onWheel = (e: WheelEvent) => {
			if (Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;

			const delta =
				e.deltaMode === WheelEvent.DOM_DELTA_LINE
					? e.deltaY * 16
					: e.deltaMode === WheelEvent.DOM_DELTA_PAGE
						? e.deltaY * el.clientWidth
						: e.deltaY;
			const maxScrollLeft = el.scrollWidth - el.clientWidth;
			const nextScrollLeft = Math.min(maxScrollLeft, Math.max(0, el.scrollLeft + delta));

			if (nextScrollLeft === el.scrollLeft) return;

			el.scrollLeft = nextScrollLeft;
			e.preventDefault();
		};

		el.addEventListener("wheel", onWheel, { passive: false });
		const observer = new MutationObserver(schedule);
		observer.observe(el, { childList: true });

		return () => {
			el.removeEventListener("wheel", onWheel);
			observer.disconnect();
			if (frame !== undefined) cancelAnimationFrame(frame);
		};
	}, []);

	// When the user activates a tab that's currently off-screen (e.g. clicked
	// from the sidebar), nudge the scroller minimally so the active tab is in view.
	useEffect(() => {
		if (!scrollRef.current || !activeTabId) return;
		const scroller = scrollRef.current;
		const activeEl = scroller.querySelector<HTMLElement>(`[data-tab-id="${activeTabId}"]`);
		if (!activeEl) return;

		const viewLeft = scroller.scrollLeft;
		const viewRight = viewLeft + scroller.clientWidth;
		const tabLeft = activeEl.offsetLeft;
		const tabRight = tabLeft + activeEl.offsetWidth;

		if (tabLeft < viewLeft) {
			scroller.scrollTo({ left: tabLeft, behavior: "smooth" });
			return;
		}

		if (tabRight > viewRight) {
			scroller.scrollTo({ left: tabRight - scroller.clientWidth, behavior: "smooth" });
		}
	}, [activeTabId]);

	return (
		<div
			className={cn(
				"mb-0 flex h-12 items-center shrink-0 px-1 gap-0.5 select-none border-b bg-panel",
				className
			)}
		>
			{leftActions ? <div className="flex items-center gap-0.5 shrink-0">{leftActions}</div> : null}
			<div
				ref={scrollRef}
				className="flex h-8 items-center flex-1 gap-0 pl-2 overflow-x-auto overflow-y-hidden scrollbar-hide [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden py-0"
			>
				{tabs.map((tab, index) => {
					const isActive = tab.id === activeTabId;

					return (
						<Fragment key={tab.id}>
							{index > 0 ? (
								<div
									aria-hidden="true"
									className={cn(
										"mx-1.5 h-4 w-px shrink-0 bg-muted-foreground/20 transition-opacity duration-150 dark:bg-muted-foreground/25",
										shouldHideSeparator(index) && "opacity-0"
									)}
								/>
							) : null}
							<div
								data-tab-id={tab.id}
								className="group relative h-full w-[180px] shrink-0"
							>
								<Button
									type="button"
									variant="ghost"
									onClick={() => handleTabClick(tab)}
									onMouseEnter={() => setHoveredTabIndex(index)}
									onMouseLeave={() => setHoveredTabIndex(null)}
									className={cn(
										"h-full w-full justify-start overflow-hidden px-3 text-left text-[13px] font-medium transition-colors duration-150",
										isActive
											? "bg-accent text-accent-foreground"
											: "bg-transparent text-muted-foreground hover:bg-accent hover:text-accent-foreground group-hover:bg-accent group-hover:text-accent-foreground group-focus-within:bg-accent group-focus-within:text-accent-foreground"
									)}
								>
									<span className="block min-w-0 flex-1 truncate text-left">{tab.title}</span>
								</Button>
								{/* Hover-only gradient + close overlay (sidebar pattern) — keeps pill width fixed and avoids ellipsis shift. */}
								<div
									className={cn(
										"pointer-events-none absolute right-0 top-0 bottom-0 flex items-center rounded-r-md pl-8 pr-2 opacity-0 transition-opacity duration-150",
										"group-hover:opacity-100 group-focus-within:opacity-100",
										"bg-gradient-to-l from-accent from-60% to-transparent"
									)}
								>
									<Button
										type="button"
										variant="ghost"
										size="icon"
										onClick={(e) => handleTabClose(e, tab.id)}
										onMouseEnter={() => setHoveredTabIndex(index)}
										onMouseLeave={() => setHoveredTabIndex(null)}
										className="pointer-events-auto size-4 rounded-full p-0.5 hover:bg-accent hover:text-accent-foreground"
									>
										<X data-icon="inline-start" />
									</Button>
								</div>
							</div>
						</Fragment>
					);
				})}
				{onNewChat && (
					<div
						className={cn(
							// Solid bg + soft left-fade so tabs scrolling underneath the
							// + button get visually masked into the bar's background.
							"sticky right-0 z-10 ml-3 flex h-full shrink-0 items-center bg-panel pl-3 pr-1",
							"before:content-[''] before:absolute before:inset-y-0 before:-left-4 before:w-4 before:pointer-events-none",
							"before:bg-gradient-to-r before:from-transparent before:to-panel"
						)}
					>
						<Button
							type="button"
							variant="ghost"
							size="icon"
							onClick={onNewChat}
							className="size-8 shrink-0 text-muted-foreground transition-all duration-150 hover:bg-accent hover:text-accent-foreground"
							title="New Chat"
						>
							<Plus data-icon="inline-start" />
						</Button>
					</div>
				)}
			</div>
			{rightActions ? (
				<div className="flex items-center gap-0.5 shrink-0 pr-2">{rightActions}</div>
			) : null}
		</div>
	);
}
