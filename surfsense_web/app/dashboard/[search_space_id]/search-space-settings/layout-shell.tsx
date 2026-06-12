"use client";

import {
	BookText,
	CircleUser,
	Cpu,
	Earth,
	UserKey,
} from "lucide-react";
import Link from "next/link";
import { useSelectedLayoutSegment } from "next/navigation";
import { useTranslations } from "next-intl";
import type React from "react";
import { useCallback, useMemo, useState } from "react";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

export type SearchSpaceSettingsTab =
	| "general"
	| "models"
	| "team-roles"
	| "prompts"
	| "public-links";

const DEFAULT_TAB: SearchSpaceSettingsTab = "general";

interface SearchSpaceSettingsLayoutShellProps {
	searchSpaceId: string;
	children: React.ReactNode;
}

export function SearchSpaceSettingsLayoutShell({
	searchSpaceId,
	children,
}: SearchSpaceSettingsLayoutShellProps) {
	const t = useTranslations("searchSpaceSettings");
	const segment = useSelectedLayoutSegment();
	const [tabScrollPos, setTabScrollPos] = useState<"start" | "middle" | "end">("start");

	const handleTabScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
		const el = e.currentTarget;
		const atStart = el.scrollLeft <= 2;
		const atEnd = el.scrollWidth - el.scrollLeft - el.clientWidth <= 2;
		setTabScrollPos(atStart ? "start" : atEnd ? "end" : "middle");
	}, []);

	const navItems = useMemo(
		() => [
			{
				value: "general" as const,
				label: t("nav_general"),
				icon: <CircleUser className="h-4 w-4" />,
			},
			{
				value: "models" as const,
				label: t("nav_models"),
				icon: <Cpu className="h-4 w-4" />,
			},
			{
				value: "team-roles" as const,
				label: t("nav_team_roles"),
				icon: <UserKey className="h-4 w-4" />,
			},
			{
				value: "prompts" as const,
				label: t("nav_system_instructions"),
				icon: <BookText className="h-4 w-4" />,
			},
			{
				value: "public-links" as const,
				label: t("nav_public_links"),
				icon: <Earth className="h-4 w-4" />,
			},
		],
		[t]
	);

	const activeTab: SearchSpaceSettingsTab =
		segment && navItems.some((item) => item.value === segment)
			? (segment as SearchSpaceSettingsTab)
			: DEFAULT_TAB;
	const selectedLabel = navItems.find((item) => item.value === activeTab)?.label ?? t("title");

	const hrefFor = (tab: SearchSpaceSettingsTab) =>
		`/dashboard/${searchSpaceId}/search-space-settings/${tab}`;

	return (
		<section className="flex h-full min-h-[min(680px,calc(100vh-5rem))] w-full select-none flex-col gap-6 md:pt-6 md:flex-row">
			<div className="md:w-[220px] md:shrink-0">
				<h1 className="mb-4 px-1 text-2xl font-semibold tracking-tight">{t("title")}</h1>
				<nav className="hidden flex-col gap-0.5 md:flex">
					{navItems.map((item) => (
						<Link
							key={item.value}
							href={hrefFor(item.value)}
							replace
							scroll={false}
							prefetch
							className={cn(
								"inline-flex h-auto items-center justify-start gap-3 rounded-md px-3 py-2.5 text-left text-sm font-medium transition-colors duration-150 focus:outline-none focus-visible:outline-none",
								activeTab === item.value
									? "bg-accent text-accent-foreground"
									: "bg-transparent text-muted-foreground hover:bg-accent hover:text-accent-foreground"
							)}
						>
							{item.icon}
							{item.label}
						</Link>
					))}
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
						{navItems.map((item) => (
							<Link
								key={item.value}
								href={hrefFor(item.value)}
								replace
								scroll={false}
								prefetch
								className={cn(
									"inline-flex h-auto shrink-0 items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition-colors duration-150 focus:outline-none focus-visible:outline-none",
									activeTab === item.value
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
					<Separator className="mt-4" />
				</div>
				<div className="min-w-0 pt-4 md:max-w-3xl">{children}</div>
			</div>
		</section>
	);
}
