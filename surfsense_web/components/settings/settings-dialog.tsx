"use client";

import type * as React from "react";
import { useCallback, useRef, useState } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

interface NavItem {
	value: string;
	label: string;
	icon: React.ReactNode;
}

interface SettingsDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	title: string;
	navItems: NavItem[];
	activeItem: string;
	onItemChange: (value: string) => void;
	children: React.ReactNode;
}

export function SettingsDialog({
	open,
	onOpenChange,
	title,
	navItems,
	activeItem,
	onItemChange,
	children,
}: SettingsDialogProps) {
	const activeRef = useRef<HTMLButtonElement>(null);
	const [tabScrollPos, setTabScrollPos] = useState<"start" | "middle" | "end">("start");

	const handleTabScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
		const el = e.currentTarget;
		const atStart = el.scrollLeft <= 2;
		const atEnd = el.scrollWidth - el.scrollLeft - el.clientWidth <= 2;
		setTabScrollPos(atStart ? "start" : atEnd ? "end" : "middle");
	}, []);

	const handleItemChange = (value: string) => {
		onItemChange(value);
		activeRef.current?.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="select-none max-w-[900px] w-[95vw] md:w-[90vw] h-[90vh] md:h-[80vh] max-h-[640px] flex flex-col md:flex-row p-0 gap-0 overflow-hidden [--card:var(--background)] dark:[--card:oklch(0.205_0_0)] dark:[--background:oklch(0.205_0_0)]">
				<DialogTitle className="sr-only">{title}</DialogTitle>

				{/* Desktop: Left sidebar */}
				<nav className="hidden md:flex w-[220px] shrink-0 flex-col border-r border-border p-3 pt-6">
					<div className="flex flex-col gap-0.5">
						{navItems.map((item) => (
							<button
								key={item.value}
								type="button"
								onClick={() => onItemChange(item.value)}
								className={cn(
									"flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors text-left focus:outline-none focus-visible:outline-none",
									activeItem === item.value
										? "bg-accent text-accent-foreground"
										: "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
								)}
							>
								{item.icon}
								{item.label}
							</button>
						))}
					</div>
				</nav>

				{/* Mobile: Top header + horizontal tabs */}
				<div className="flex md:hidden flex-col shrink-0">
					<div className="px-4 pt-4 pb-2">
						<h2 className="text-base font-semibold">{title}</h2>
					</div>
					<div
						className="overflow-x-auto scrollbar-hide border-b border-border"
						onScroll={handleTabScroll}
						style={{
							maskImage: `linear-gradient(to right, ${tabScrollPos === "start" ? "black" : "transparent"}, black 24px, black calc(100% - 24px), ${tabScrollPos === "end" ? "black" : "transparent"})`,
							WebkitMaskImage: `linear-gradient(to right, ${tabScrollPos === "start" ? "black" : "transparent"}, black 24px, black calc(100% - 24px), ${tabScrollPos === "end" ? "black" : "transparent"})`,
						}}
					>
						<div className="flex gap-1 px-4 pb-2">
							{navItems.map((item) => (
								<button
									key={item.value}
									ref={activeItem === item.value ? activeRef : undefined}
									type="button"
									onClick={() => handleItemChange(item.value)}
									className={cn(
										"flex items-center gap-2 whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium transition-colors shrink-0 focus:outline-none focus-visible:outline-none",
										activeItem === item.value
											? "bg-accent text-accent-foreground"
											: "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
									)}
								>
									{item.icon}
									{item.label}
								</button>
							))}
						</div>
					</div>
				</div>

				{/* Content area */}
				<div className="flex flex-1 flex-col overflow-hidden min-w-0">
					<div className="hidden md:block px-8 pt-6 pb-2">
						<h2 className="text-lg font-semibold">
							{navItems.find((i) => i.value === activeItem)?.label ?? title}
						</h2>
						<Separator className="mt-4" />
					</div>
					<div className="flex-1 overflow-y-auto overflow-x-hidden">
						<div className="px-4 md:px-8 pb-6 pt-4 md:pt-0 min-w-0">{children}</div>
					</div>
				</div>
			</DialogContent>
		</Dialog>
	);
}
