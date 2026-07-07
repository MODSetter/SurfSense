"use client";

import { ChevronRight, History, LayoutGrid } from "lucide-react";
import Link from "next/link";
import { useSelectedLayoutSegments } from "next/navigation";
import type React from "react";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Drawer,
	DrawerContent,
	DrawerHandle,
	DrawerTitle,
	DrawerTrigger,
} from "@/components/ui/drawer";
import { Separator } from "@/components/ui/separator";
import { PLAYGROUND_PLATFORMS, type PlaygroundPlatform, type PlaygroundVerb } from "@/lib/playground/catalog";
import { cn } from "@/lib/utils";

interface PlaygroundLayoutShellProps {
	workspaceId: string;
	children: React.ReactNode;
}

interface TopLevelNavItem {
	value: "overview" | "runs";
	label: string;
	href: string;
	icon: React.ReactNode;
}

function TopLevelNavLink({
	item,
	activeValue,
	onNavigate,
}: {
	item: TopLevelNavItem;
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

function ProviderNavGroup({
	platform,
	base,
	activeValue,
	isExpanded,
	onToggle,
	onNavigate,
}: {
	platform: PlaygroundPlatform;
	base: string;
	activeValue: string;
	isExpanded: boolean;
	onToggle: () => void;
	onNavigate?: () => void;
}) {
	const Icon = platform.icon;

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
				<Icon className="h-4 w-4 shrink-0" />
				<span className="min-w-0 truncate">{platform.label}</span>
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
						{platform.verbs.map((verb) => {
							const value = `${platform.id}/${verb.verb}`;
							const isActive = activeValue === value;
							return (
								<Link
									key={value}
									href={`${base}/${platform.id}/${verb.verb}`}
									replace
									scroll={false}
									prefetch
									onClick={onNavigate}
									className={cn(
										"inline-flex h-auto items-center justify-start rounded-md px-3 py-2 text-left text-sm font-medium transition-colors duration-150 focus:outline-none focus-visible:outline-none",
										isActive
											? "bg-accent text-accent-foreground"
											: "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
									)}
								>
									<span className="min-w-0 truncate">{verb.label}</span>
								</Link>
							);
						})}
					</div>
				</div>
			</div>
		</div>
	);
}

export function PlaygroundLayoutShell({ workspaceId, children }: PlaygroundLayoutShellProps) {
	const segments = useSelectedLayoutSegments();
	const base = `/dashboard/${workspaceId}/playground`;
	const activePlatform = PLAYGROUND_PLATFORMS.some((platform) => platform.id === segments[0])
		? segments[0]
		: null;
	const [expandedProvider, setExpandedProvider] = useState<string | null>(activePlatform);
	const [mobileNavOpen, setMobileNavOpen] = useState(false);

	useEffect(() => {
		if (activePlatform) {
			setExpandedProvider(activePlatform);
		}
	}, [activePlatform]);

	const topLevelItems = useMemo<TopLevelNavItem[]>(
		() => [
			{
				value: "overview",
				label: "Overview",
				href: base,
				icon: <LayoutGrid className="h-4 w-4" />,
			},
			{
				value: "runs",
				label: "Runs",
				href: `${base}/runs`,
				icon: <History className="h-4 w-4" />,
			},
		],
		[base]
	);

	const activeValue =
		segments.length >= 2
			? `${segments[0]}/${segments[1]}`
			: segments[0] && topLevelItems.some((item) => item.value === segments[0])
				? segments[0]
				: "overview";

	const selectedLabel = getSelectedLabel(activeValue, topLevelItems);

	const renderNav = (onNavigate?: () => void) => (
		<>
			{topLevelItems.map((item) => (
				<TopLevelNavLink
					key={item.value}
					item={item}
					activeValue={activeValue}
					onNavigate={onNavigate}
				/>
			))}
			<Separator className="my-3 bg-border" />
			<div className="flex flex-col gap-0.5">
				{PLAYGROUND_PLATFORMS.map((platform) => (
					<ProviderNavGroup
						key={platform.id}
						platform={platform}
						base={base}
						activeValue={activeValue}
						isExpanded={expandedProvider === platform.id}
						onToggle={() =>
							setExpandedProvider((current) => (current === platform.id ? null : platform.id))
						}
						onNavigate={onNavigate}
					/>
				))}
			</div>
		</>
	);

	return (
		<section className="flex h-full min-h-[min(680px,calc(100vh-5rem))] w-full select-none flex-col gap-6 md:flex-row">
			<div className="md:w-[220px] md:shrink-0">
				<h1 className="mb-4 px-1 text-xl font-semibold tracking-tight text-foreground md:text-2xl">
					API Playground
				</h1>
				<nav className="hidden flex-col gap-0.5 md:flex">
					{renderNav()}
				</nav>
				<Drawer open={mobileNavOpen} onOpenChange={setMobileNavOpen} shouldScaleBackground={false}>
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
						<DrawerTitle className="sr-only">API Playground navigation</DrawerTitle>
						<nav className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto p-4">
							{renderNav(() => setMobileNavOpen(false))}
						</nav>
					</DrawerContent>
				</Drawer>
			</div>

			<div className="min-w-0 flex-1">
				<div className="hidden md:block">
					<h2 className="text-lg font-semibold">{selectedLabel}</h2>
					<Separator className="mt-4 bg-border" />
				</div>
				<div className="min-w-0 pt-4">{children}</div>
			</div>
		</section>
	);
}

function getSelectedLabel(activeValue: string, topLevelItems: TopLevelNavItem[]): string {
	const topLevelItem = topLevelItems.find((item) => item.value === activeValue);
	if (topLevelItem) return topLevelItem.label;

	const [platformId, verbId] = activeValue.split("/");
	const platform = PLAYGROUND_PLATFORMS.find((item) => item.id === platformId);
	const verb: PlaygroundVerb | undefined = platform?.verbs.find((item) => item.verb === verbId);

	if (platform && verb) return `${platform.label} / ${verb.label}`;
	return "API Playground";
}
