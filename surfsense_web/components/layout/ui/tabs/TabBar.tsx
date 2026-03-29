"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { FileText, MessageSquare, Plus, X } from "lucide-react";
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
	className?: string;
}

export function TabBar({ onTabSwitch, onNewChat, className }: TabBarProps) {
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

	// Scroll active tab into view
	useEffect(() => {
		if (!scrollRef.current || !activeTabId) return;
		const activeEl = scrollRef.current.querySelector(`[data-tab-id="${activeTabId}"]`);
		if (activeEl) {
			activeEl.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
		}
	}, [activeTabId]);

	// Only show tab bar when there's more than one tab
	if (tabs.length <= 1) return null;

	return (
		<div className={cn("flex h-12 items-stretch shrink-0 border-b bg-main-panel", className)}>
			<div
				ref={scrollRef}
				className="flex h-full items-stretch flex-1 overflow-x-auto overflow-y-hidden scrollbar-hide [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
			>
				{tabs.map((tab) => {
					const isActive = tab.id === activeTabId;
					const Icon = tab.type === "document" ? FileText : MessageSquare;

					return (
						<button
							key={tab.id}
							type="button"
							data-tab-id={tab.id}
							onClick={() => handleTabClick(tab)}
							className={cn(
								"group relative flex h-full items-center self-stretch gap-1.5 px-3 min-w-0 max-w-[200px] text-xs font-medium border-r transition-colors shrink-0",
								isActive
									? "bg-muted/40 text-foreground"
									: "bg-transparent text-muted-foreground hover:bg-muted/25 hover:text-foreground"
							)}
						>
							{isActive && <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-primary" />}
							<Icon className="size-3.5 shrink-0" />
							<span className="truncate">{tab.title}</span>
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
									"ml-auto shrink-0 rounded-sm p-0.5 transition-colors",
									isActive
										? "opacity-60 hover:opacity-100 hover:bg-muted"
										: "opacity-0 group-hover:opacity-60 hover:opacity-100! hover:bg-muted"
								)}
							>
								<X className="size-3" />
							</span>
						</button>
					);
				})}
				{onNewChat && (
					<div className="flex h-full items-center px-1.5 shrink-0">
						<button
							type="button"
							onClick={onNewChat}
							className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground hover:bg-muted/60"
							title="New Chat"
						>
							<Plus className="size-3.5" />
						</button>
					</div>
				)}
			</div>
		</div>
	);
}
