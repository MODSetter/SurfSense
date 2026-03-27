"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { FileText, MessageSquare, Plus, X } from "lucide-react";
import { useCallback, useRef, useEffect } from "react";
import {
	activeTabIdAtom,
	closeTabAtom,
	switchTabAtom,
	tabsAtom,
	type Tab,
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
		<div
			className={cn(
				"flex items-center shrink-0 border-b bg-main-panel",
				className
			)}
		>
			<div
				ref={scrollRef}
				className="flex items-center flex-1 overflow-x-auto scrollbar-none"
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
								"group relative flex items-center gap-1.5 px-3 h-9 min-w-0 max-w-[200px] text-xs font-medium border-r transition-colors shrink-0",
								isActive
									? "bg-main-panel text-foreground"
									: "bg-muted/30 text-muted-foreground hover:bg-muted/60 hover:text-foreground"
							)}
						>
							{isActive && (
								<span className="absolute bottom-0 left-0 right-0 h-[2px] bg-primary" />
							)}
							<Icon className="size-3.5 shrink-0" />
							<span className="truncate">{tab.title}</span>
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
			</div>

			{onNewChat && (
				<button
					type="button"
					onClick={onNewChat}
					className="flex items-center justify-center size-9 shrink-0 text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
					title="New Chat"
				>
					<Plus className="size-3.5" />
				</button>
			)}
		</div>
	);
}
