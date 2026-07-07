"use client";

import { History, LayoutGrid } from "lucide-react";
import Link from "next/link";
import { useSelectedLayoutSegments } from "next/navigation";
import type React from "react";
import { useCallback, useMemo, useState } from "react";
import { Separator } from "@/components/ui/separator";
import { PLAYGROUND_PLATFORMS, type PlatformIcon } from "@/lib/playground/catalog";
import { cn } from "@/lib/utils";

interface PlaygroundLayoutShellProps {
	workspaceId: string;
	children: React.ReactNode;
}

type PlaygroundNavItem =
	| {
			type: "item";
			value: string;
			label: string;
			href: string;
			icon: React.ReactNode;
			indented?: boolean;
	  }
	| {
			type: "section";
			value: string;
			label: string;
			icon: PlatformIcon;
	  };

function PlaygroundNavLink({
	item,
	activeValue,
}: {
	item: Extract<PlaygroundNavItem, { type: "item" }>;
	activeValue: string;
}) {
	const isActive = activeValue === item.value;

	return (
		<Link
			href={item.href}
			replace
			scroll={false}
			prefetch
			className={cn(
				"inline-flex h-auto items-center justify-start gap-3 rounded-md px-3 py-2.5 text-left text-sm font-medium transition-colors duration-150 focus:outline-none focus-visible:outline-none",
				item.indented && "pl-9",
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

export function PlaygroundLayoutShell({ workspaceId, children }: PlaygroundLayoutShellProps) {
	const segments = useSelectedLayoutSegments();
	const [tabScrollPos, setTabScrollPos] = useState<"start" | "middle" | "end">("start");
	const base = `/dashboard/${workspaceId}/playground`;

	const handleTabScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
		const el = e.currentTarget;
		const atStart = el.scrollLeft <= 2;
		const atEnd = el.scrollWidth - el.scrollLeft - el.clientWidth <= 2;
		setTabScrollPos(atStart ? "start" : atEnd ? "end" : "middle");
	}, []);

	const navItems = useMemo<PlaygroundNavItem[]>(
		() => [
			{
				type: "item",
				value: "overview",
				label: "Overview",
				href: base,
				icon: <LayoutGrid className="h-4 w-4" />,
			},
			{
				type: "item",
				value: "runs",
				label: "Runs",
				href: `${base}/runs`,
				icon: <History className="h-4 w-4" />,
			},
			...PLAYGROUND_PLATFORMS.flatMap<PlaygroundNavItem>((platform) => [
				{
					type: "section",
					value: platform.id,
					label: platform.label,
					icon: platform.icon,
				},
				...platform.verbs.map((verb) => ({
					type: "item" as const,
					value: `${platform.id}/${verb.verb}`,
					label: verb.label,
					href: `${base}/${platform.id}/${verb.verb}`,
					icon: <span className="h-4 w-4" />,
					indented: true,
				})),
			]),
		],
		[base]
	);

	const activeValue =
		segments.length >= 2
			? `${segments[0]}/${segments[1]}`
			: segments[0] && navItems.some((item) => item.type === "item" && item.value === segments[0])
				? segments[0]
				: "overview";
	const selectedLabel =
		navItems.find((item) => item.type === "item" && item.value === activeValue)?.label ??
		"API Playground";
	const mobileItems = navItems.filter(
		(item): item is Extract<PlaygroundNavItem, { type: "item" }> => item.type === "item"
	);

	return (
		<section className="flex h-full min-h-[min(680px,calc(100vh-5rem))] w-full select-none flex-col gap-6 md:flex-row">
			<div className="md:w-[220px] md:shrink-0">
				<h1 className="mb-4 px-1 text-xl font-semibold tracking-tight text-foreground md:text-2xl">
					API Playground
				</h1>
				<nav className="hidden flex-col gap-0.5 md:flex">
					{navItems.map((item) => {
						if (item.type === "section") {
							const Icon = item.icon;
							return (
								<div
									key={item.value}
									className="mt-3 flex items-center gap-2 px-3 py-1 text-xs font-medium text-muted-foreground first:mt-1"
								>
									<Icon className="h-3.5 w-3.5 shrink-0" />
									<span className="truncate">{item.label}</span>
								</div>
							);
						}

						return <PlaygroundNavLink key={item.value} item={item} activeValue={activeValue} />;
					})}
				</nav>
				<div
					className="overflow-x-auto border-b border-border pb-3 md:hidden"
					onScroll={handleTabScroll}
					style={{
						maskImage: `linear-gradient(to right, ${tabScrollPos === "start" ? "black" : "transparent"}, black 24px, black calc(100% - 24px), ${tabScrollPos === "end" ? "black" : "transparent"})`,
						WebkitMaskImage: `linear-gradient(to right, ${tabScrollPos === "start" ? "black" : "transparent"}, black 24px, black calc(100% - 24px), ${tabScrollPos === "end" ? "black" : "transparent"})`,
					}}
				>
					<div className="flex gap-1">
						{mobileItems.map((item) => (
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
