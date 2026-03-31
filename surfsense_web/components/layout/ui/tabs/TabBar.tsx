"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { Plus, X } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import {
	activeTabIdAtom,
	closeTabAtom,
	switchTabAtom,
	type Tab,
	tabsAtom,
} from "@/atoms/tabs/tabs.atom";
import { cn } from "@/lib/utils";

interface TabBarProps {
	onTabSwitch?: (tab: Tab) => void;
	onNewChat?: () => void;
	rightActions?: React.ReactNode;
	className?: string;
}

export function TabBar({ onTabSwitch, onNewChat, rightActions, className }: TabBarProps) {
	const tabs = useAtomValue(tabsAtom);
	const activeTabId = useAtomValue(activeTabIdAtom);
	const switchTab = useSetAtom(switchTabAtom);
	const closeTab = useSetAtom(closeTabAtom);
	const scrollRef = useRef<HTMLDivElement>(null);

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

	// Keep active tab visible with minimal scroll shift.
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

	// Only show tab bar when there's more than one tab
	if (tabs.length <= 1) return null;

	return (
		<div
			className={cn(
				"mb-2 flex h-9 items-center shrink-0 px-1 gap-0.5",
				className
			)}
		>
			<div
				ref={scrollRef}
				className="flex h-full items-center flex-1 gap-0.5 overflow-x-auto overflow-y-hidden scrollbar-hide [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden py-1"
			>
				{tabs.map((tab) => {
					const isActive = tab.id === activeTabId;

					return (
						<button
							key={tab.id}
							type="button"
							data-tab-id={tab.id}
							onClick={() => handleTabClick(tab)}
							className={cn(
								"group relative flex h-full w-[150px] items-center px-3 min-h-0 overflow-hidden text-[13px] font-medium rounded-lg transition-all duration-150 shrink-0",
								isActive
									? "bg-muted/60 text-foreground"
									: "bg-transparent text-muted-foreground hover:bg-muted/30 hover:text-foreground"
							)}
						>
							<span className="block min-w-0 flex-1 truncate text-left group-hover:pr-5 group-focus-within:pr-5">
								{tab.title}
							</span>
							{/* biome-ignore lint/a11y/useSemanticElements: cannot nest button inside button */}
							<span
								role="button"
								tabIndex={0}
								onClick={(e) => handleTabClose(e, tab.id)}
								onKeyDown={(e) => {
									if (e.key === "Enter" || e.key === " ") {
										e.preventDefault();
										handleTabClose(e as unknown as React.MouseEvent, tab.id);
									}
								}}
								className={cn(
									"absolute right-2 top-1/2 -translate-y-1/2 shrink-0 rounded-full p-0.5 transition-all duration-150 hover:bg-muted-foreground/15",
									isActive
										? "opacity-0 group-hover:opacity-70 group-focus-within:opacity-70 hover:opacity-100"
										: "opacity-0 group-hover:opacity-60 group-focus-within:opacity-60 hover:opacity-100!"
								)}
							>
								<X className="size-3" />
							</span>
						</button>
					);
				})}
			</div>
			<div className="flex items-center gap-0.5 shrink-0">
				{onNewChat && (
					<button
						type="button"
						onClick={onNewChat}
						className="flex h-6 w-6 items-center justify-center shrink-0 rounded-md text-muted-foreground transition-all duration-150 hover:text-foreground hover:bg-muted/40"
						title="New Chat"
					>
						<Plus className="size-3.5" />
					</button>
				)}
				{rightActions}
			</div>
		</div>
	);
}
