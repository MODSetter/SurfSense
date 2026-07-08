"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import type React from "react";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Drawer,
	DrawerContent,
	DrawerHandle,
	DrawerTitle,
	DrawerTrigger,
} from "@/components/ui/drawer";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

export interface RoutedSectionItem {
	value: string;
	label: string;
	href: string;
	icon?: React.ReactNode;
}

export interface RoutedSectionGroup {
	value: string;
	label: string;
	icon?: React.ReactNode;
	items: RoutedSectionItem[];
}

interface RoutedSectionShellProps {
	title: string;
	items: RoutedSectionItem[];
	activeValue: string;
	selectedLabel: string;
	children: React.ReactNode;
	groups?: RoutedSectionGroup[];
	mobileNav?: "scroll" | "drawer";
	contentClassName?: string;
	desktopNav?: boolean;
}

function findActiveGroupValue(groups: RoutedSectionGroup[], activeValue: string): string | null {
	return (
		groups.find((group) => group.items.some((item) => item.value === activeValue))?.value ?? null
	);
}

function SectionNavLink({
	item,
	activeValue,
	onNavigate,
}: {
	item: RoutedSectionItem;
	activeValue: string;
	onNavigate?: () => void;
}) {
	const isActive = activeValue === item.value;

	return (
		<Link
			href={item.href}
			replace
			scroll={false}
			prefetch
			onClick={onNavigate}
			className={cn(
				"inline-flex h-auto items-center justify-start gap-3 rounded-md px-3 py-2.5 text-left text-sm font-medium transition-colors duration-150 focus:outline-none focus-visible:outline-none",
				isActive
					? "bg-accent text-accent-foreground"
					: "bg-transparent text-muted-foreground hover:bg-accent hover:text-accent-foreground"
			)}
		>
			{item.icon}
			<span className="min-w-0 truncate">{item.label}</span>
		</Link>
	);
}

function SectionNavGroup({
	group,
	activeValue,
	isExpanded,
	onToggle,
	onNavigate,
}: {
	group: RoutedSectionGroup;
	activeValue: string;
	isExpanded: boolean;
	onToggle: () => void;
	onNavigate?: () => void;
}) {
	return (
		<div className="flex flex-col gap-0.5">
			<button
				type="button"
				aria-expanded={isExpanded}
				onClick={onToggle}
				className={cn(
					"inline-flex h-auto items-center justify-start gap-3 rounded-md px-3 py-2.5 text-left text-sm font-medium transition-colors duration-150 focus:outline-none focus-visible:outline-none",
					isExpanded
						? "text-accent-foreground"
						: "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
				)}
			>
				{group.icon}
				<span className="min-w-0 truncate">{group.label}</span>
				<ChevronRight
					className={cn("ml-auto h-4 w-4 shrink-0 transition-transform", isExpanded && "rotate-90")}
				/>
			</button>
			<div
				className={cn(
					"grid overflow-hidden transition-[grid-template-rows,opacity] duration-200 ease-out",
					isExpanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
				)}
				aria-hidden={!isExpanded}
			>
				<div className="min-h-0 overflow-hidden">
					<div className="flex flex-col gap-0.5 pl-10">
						{group.items.map((item) => (
							<SectionNavLink
								key={item.value}
								item={item}
								activeValue={activeValue}
								onNavigate={onNavigate}
							/>
						))}
					</div>
				</div>
			</div>
		</div>
	);
}

export function RoutedSectionShell({
	title,
	items,
	activeValue,
	selectedLabel,
	children,
	groups = [],
	mobileNav = "scroll",
	contentClassName,
	desktopNav = true,
}: RoutedSectionShellProps) {
	const [tabScrollPos, setTabScrollPos] = useState<"start" | "middle" | "end">("start");
	const [drawerOpen, setDrawerOpen] = useState(false);
	const [expandedGroup, setExpandedGroup] = useState<string | null>(() =>
		findActiveGroupValue(groups, activeValue)
	);

	useEffect(() => {
		const activeGroup = findActiveGroupValue(groups, activeValue);
		if (activeGroup) {
			setExpandedGroup(activeGroup);
		}
	}, [activeValue, groups]);

	const handleTabScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
		const el = e.currentTarget;
		const atStart = el.scrollLeft <= 2;
		const atEnd = el.scrollWidth - el.scrollLeft - el.clientWidth <= 2;
		setTabScrollPos(atStart ? "start" : atEnd ? "end" : "middle");
	}, []);

	const renderNav = (onNavigate?: () => void) => (
		<>
			{items.map((item) => (
				<SectionNavLink
					key={item.value}
					item={item}
					activeValue={activeValue}
					onNavigate={onNavigate}
				/>
			))}
			{groups.length > 0 && (
				<>
					<Separator className="my-3 bg-border" />
					<div className="flex flex-col gap-0.5">
						{groups.map((group) => (
							<SectionNavGroup
								key={group.value}
								group={group}
								activeValue={activeValue}
								isExpanded={expandedGroup === group.value}
								onToggle={() =>
									setExpandedGroup((current) => (current === group.value ? null : group.value))
								}
								onNavigate={onNavigate}
							/>
						))}
					</div>
				</>
			)}
		</>
	);

	return (
		<section
			className={cn(
				"flex h-full min-h-[min(680px,calc(100vh-5rem))] w-full select-none flex-col",
				desktopNav ? "gap-6 md:flex-row" : "gap-4 md:block"
			)}
		>
			<div className={cn("md:w-[220px] md:shrink-0", !desktopNav && "md:hidden")}>
				<h1 className="mb-4 px-1 text-xl font-semibold tracking-tight text-foreground md:text-2xl">
					{title}
				</h1>
				{desktopNav ? <nav className="hidden flex-col gap-0.5 md:flex">{renderNav()}</nav> : null}
				{mobileNav === "drawer" ? (
					<Drawer open={drawerOpen} onOpenChange={setDrawerOpen} shouldScaleBackground={false}>
						<DrawerTrigger asChild>
							<Button
								type="button"
								variant="outline"
								className="flex h-10 w-full justify-between bg-transparent px-3 hover:bg-accent md:hidden"
							>
								<span className="truncate">{selectedLabel}</span>
								<ChevronRight className="h-4 w-4 rotate-90 text-muted-foreground" />
							</Button>
						</DrawerTrigger>
						<DrawerContent className="h-[88vh] overflow-hidden rounded-t-2xl border bg-popover text-popover-foreground">
							<DrawerHandle className="mt-3 h-1.5 w-10" />
							<DrawerTitle className="sr-only">{title} navigation</DrawerTitle>
							<nav className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto p-4">
								{renderNav(() => setDrawerOpen(false))}
							</nav>
						</DrawerContent>
					</Drawer>
				) : (
					<div
						className="overflow-x-auto border-b border-border pb-3 md:hidden"
						onScroll={handleTabScroll}
						style={{
							maskImage: `linear-gradient(to right, ${tabScrollPos === "start" ? "black" : "transparent"}, black 24px, black calc(100% - 24px), ${tabScrollPos === "end" ? "black" : "transparent"})`,
							WebkitMaskImage: `linear-gradient(to right, ${tabScrollPos === "start" ? "black" : "transparent"}, black 24px, black calc(100% - 24px), ${tabScrollPos === "end" ? "black" : "transparent"})`,
						}}
					>
						<div className="flex gap-1">
							{items.map((item) => (
								<Link
									key={item.value}
									href={item.href}
									replace
									scroll={false}
									prefetch
									className={cn(
										"inline-flex h-auto shrink-0 items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition-colors duration-150 focus:outline-none focus-visible:outline-none",
										activeValue === item.value
											? "bg-accent text-accent-foreground"
											: "bg-transparent text-muted-foreground hover:bg-accent hover:text-accent-foreground"
									)}
								>
									{item.icon}
									{item.label}
								</Link>
							))}
						</div>
					</div>
				)}
			</div>

			<div className="min-w-0 flex-1">
				{desktopNav ? (
					<div className="hidden md:block">
						<h2 className="text-lg font-semibold">{selectedLabel}</h2>
						<Separator className="mt-4 bg-border" />
					</div>
				) : null}
				<div className={cn("min-w-0", desktopNav ? "pt-4" : "pt-4 md:pt-0", contentClassName)}>
					{children}
				</div>
			</div>
		</section>
	);
}
