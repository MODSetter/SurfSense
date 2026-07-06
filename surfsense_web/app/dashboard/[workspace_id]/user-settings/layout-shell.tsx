"use client";

import {
	CircleUser,
	Keyboard,
	KeyRound,
	Library,
	MessageCircle,
	Monitor,
	ReceiptText,
	ShieldCheck,
	WandSparkles,
} from "lucide-react";
import Link from "next/link";
import { useSelectedLayoutSegment } from "next/navigation";
import { useTranslations } from "next-intl";
import type React from "react";
import { useCallback, useMemo, useState } from "react";
import { Separator } from "@/components/ui/separator";
import { usePlatform } from "@/hooks/use-platform";
import { cn } from "@/lib/utils";

export type UserSettingsTab =
	| "profile"
	| "api-key"
	| "prompts"
	| "community-prompts"
	| "agent-permissions"
	| "purchases"
	| "desktop"
	| "hotkeys"
	| "messaging-channels";

const DEFAULT_TAB: UserSettingsTab = "profile";

interface UserSettingsLayoutShellProps {
	workspaceId: string;
	children: React.ReactNode;
}

export function UserSettingsLayoutShell({ workspaceId, children }: UserSettingsLayoutShellProps) {
	const t = useTranslations("userSettings");
	const { isDesktop } = usePlatform();
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
				value: "profile" as const,
				label: t("profile_nav_label"),
				icon: <CircleUser className="h-4 w-4" />,
			},
			{
				value: "api-key" as const,
				label: t("api_key_nav_label"),
				icon: <KeyRound className="h-4 w-4" />,
			},
			{
				value: "prompts" as const,
				label: "My Prompts",
				icon: <WandSparkles className="h-4 w-4" />,
			},
			{
				value: "community-prompts" as const,
				label: "Community Prompts",
				icon: <Library className="h-4 w-4" />,
			},
			{
				value: "agent-permissions" as const,
				label: "Agent Permissions",
				icon: <ShieldCheck className="h-4 w-4" />,
			},
			{
				value: "messaging-channels" as const,
				label: "Messaging Channels",
				icon: <MessageCircle className="h-4 w-4" />,
			},
			{
				value: "purchases" as const,
				label: "Purchase History",
				icon: <ReceiptText className="h-4 w-4" />,
			},
			...(isDesktop
				? [
						{
							value: "desktop" as const,
							label: "App Preferences",
							icon: <Monitor className="h-4 w-4" />,
						},
						{
							value: "hotkeys" as const,
							label: "Hotkeys",
							icon: <Keyboard className="h-4 w-4" />,
						},
					]
				: []),
		],
		[t, isDesktop]
	);

	const activeTab: UserSettingsTab =
		segment && navItems.some((item) => item.value === segment)
			? (segment as UserSettingsTab)
			: DEFAULT_TAB;
	const selectedLabel = navItems.find((item) => item.value === activeTab)?.label ?? t("title");

	const hrefFor = (tab: UserSettingsTab) => `/dashboard/${workspaceId}/user-settings/${tab}`;

	return (
		<section className="flex h-full min-h-[min(680px,calc(100vh-5rem))] w-full select-none flex-col gap-6 md:flex-row">
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
					<Separator className="mt-4 bg-border" />
				</div>
				<div className="min-w-0 pt-4 md:max-w-3xl">{children}</div>
			</div>
		</section>
	);
}
