"use client";

import {
	Brain,
	CircleUser,
	Globe,
	Keyboard,
	KeyRound,
	Monitor,
	ReceiptText,
	ShieldCheck,
	Sparkles,
	Workflow,
} from "lucide-react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { usePlatform } from "@/hooks/use-platform";
import { cn } from "@/lib/utils";

const ProfileContent = dynamic(
	() =>
		import("@/app/dashboard/[search_space_id]/user-settings/components/ProfileContent").then(
			(m) => ({ default: m.ProfileContent })
		),
	{ ssr: false }
);
const ApiKeyContent = dynamic(
	() =>
		import("@/app/dashboard/[search_space_id]/user-settings/components/ApiKeyContent").then(
			(m) => ({ default: m.ApiKeyContent })
		),
	{ ssr: false }
);
const PromptsContent = dynamic(
	() =>
		import("@/app/dashboard/[search_space_id]/user-settings/components/PromptsContent").then(
			(m) => ({ default: m.PromptsContent })
		),
	{ ssr: false }
);
const CommunityPromptsContent = dynamic(
	() =>
		import(
			"@/app/dashboard/[search_space_id]/user-settings/components/CommunityPromptsContent"
		).then((m) => ({ default: m.CommunityPromptsContent })),
	{ ssr: false }
);
const PurchaseHistoryContent = dynamic(
	() =>
		import(
			"@/app/dashboard/[search_space_id]/user-settings/components/PurchaseHistoryContent"
		).then((m) => ({ default: m.PurchaseHistoryContent })),
	{ ssr: false }
);
const DesktopContent = dynamic(
	() =>
		import("@/app/dashboard/[search_space_id]/user-settings/components/DesktopContent").then(
			(m) => ({ default: m.DesktopContent })
		),
	{ ssr: false }
);
const DesktopShortcutsContent = dynamic(
	() =>
		import(
			"@/app/dashboard/[search_space_id]/user-settings/components/DesktopShortcutsContent"
		).then((m) => ({ default: m.DesktopShortcutsContent })),
	{ ssr: false }
);
const MemoryContent = dynamic(
	() =>
		import("@/app/dashboard/[search_space_id]/user-settings/components/MemoryContent").then(
			(m) => ({ default: m.MemoryContent })
		),
	{ ssr: false }
);
const AgentPermissionsContent = dynamic(
	() =>
		import(
			"@/app/dashboard/[search_space_id]/user-settings/components/AgentPermissionsContent"
		).then((m) => ({ default: m.AgentPermissionsContent })),
	{ ssr: false }
);
const AgentStatusContent = dynamic(
	() =>
		import("@/app/dashboard/[search_space_id]/user-settings/components/AgentStatusContent").then(
			(m) => ({ default: m.AgentStatusContent })
		),
	{ ssr: false }
);

export type UserSettingsTab =
	| "profile"
	| "api-key"
	| "prompts"
	| "community-prompts"
	| "memory"
	| "agent-permissions"
	| "agent-status"
	| "purchases"
	| "desktop"
	| "desktop-shortcuts";

interface UserSettingsPanelProps {
	searchSpaceId: string;
	initialTab?: UserSettingsTab;
}

export function UserSettingsPanel({
	searchSpaceId,
	initialTab = "profile",
}: UserSettingsPanelProps) {
	const t = useTranslations("userSettings");
	const router = useRouter();
	const { isDesktop } = usePlatform();
	const [activeTab, setActiveTab] = useState<UserSettingsTab>(initialTab);
	const [tabScrollPos, setTabScrollPos] = useState<"start" | "middle" | "end">("start");

	useEffect(() => {
		setActiveTab(initialTab);
	}, [initialTab]);

	const handleTabScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
		const el = e.currentTarget;
		const atStart = el.scrollLeft <= 2;
		const atEnd = el.scrollWidth - el.scrollLeft - el.clientWidth <= 2;
		setTabScrollPos(atStart ? "start" : atEnd ? "end" : "middle");
	}, []);

	const navItems = useMemo(
		() => [
			{ value: "profile", label: t("profile_nav_label"), icon: <CircleUser className="h-4 w-4" /> },
			{
				value: "api-key",
				label: t("api_key_nav_label"),
				icon: <KeyRound className="h-4 w-4" />,
			},
			{
				value: "prompts",
				label: "My Prompts",
				icon: <Sparkles className="h-4 w-4" />,
			},
			{
				value: "community-prompts",
				label: "Community Prompts",
				icon: <Globe className="h-4 w-4" />,
			},
			{
				value: "memory",
				label: "Memory",
				icon: <Brain className="h-4 w-4" />,
			},
			{
				value: "agent-permissions",
				label: "Agent Permissions",
				icon: <ShieldCheck className="h-4 w-4" />,
			},
			{
				value: "agent-status",
				label: "Agent Status",
				icon: <Workflow className="h-4 w-4" />,
			},
			{
				value: "purchases",
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
							value: "desktop-shortcuts" as const,
							label: "Hotkeys",
							icon: <Keyboard className="h-4 w-4" />,
						},
					]
				: []),
		],
		[t, isDesktop]
	);

	const selectedTab = navItems.some((item) => item.value === activeTab) ? activeTab : "profile";
	const selectedLabel = navItems.find((item) => item.value === selectedTab)?.label ?? t("title");

	const handleItemChange = (tab: UserSettingsTab) => {
		setActiveTab(tab);
		const suffix = tab === "profile" ? "" : `?tab=${tab}`;
		router.replace(`/dashboard/${searchSpaceId}/user-settings${suffix}`, { scroll: false });
	};

	return (
		<section className="flex h-full min-h-[min(680px,calc(100vh-5rem))] w-full select-none flex-col gap-6 md:pt-10 md:flex-row">
			<div className="md:w-[220px] md:shrink-0">
				<h1 className="mb-4 px-1 text-2xl font-semibold tracking-tight">{t("title")}</h1>
				<nav className="hidden flex-col gap-0.5 md:flex">
					{navItems.map((item) => (
						<Button
							key={item.value}
							type="button"
							variant="ghost"
							onClick={() => handleItemChange(item.value as UserSettingsTab)}
							className={cn(
								"h-auto justify-start gap-3 px-3 py-2.5 text-left text-sm font-medium transition-colors duration-150 focus:outline-none focus-visible:outline-none",
								selectedTab === item.value
									? "bg-accent text-accent-foreground"
									: "bg-transparent text-muted-foreground hover:bg-accent hover:text-accent-foreground"
							)}
						>
							{item.icon}
							{item.label}
						</Button>
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
							<Button
								key={item.value}
								type="button"
								variant="ghost"
								onClick={() => handleItemChange(item.value as UserSettingsTab)}
								className={cn(
									"h-auto shrink-0 gap-2 px-3 py-1.5 text-xs font-medium transition-colors duration-150 focus:outline-none focus-visible:outline-none",
									selectedTab === item.value
										? "bg-accent text-accent-foreground"
										: "bg-transparent text-muted-foreground hover:bg-accent hover:text-accent-foreground"
								)}
							>
								{item.icon}
								{item.label}
							</Button>
						))}
					</div>
				</div>
			</div>

			<div className="min-w-0 flex-1">
				<div className="hidden md:block">
					<h2 className="text-lg font-semibold">{selectedLabel}</h2>
					<Separator className="mt-4 bg-border" />
				</div>
				<div className="min-w-0 pt-4 md:max-w-3xl">
					{selectedTab === "profile" && <ProfileContent />}
					{selectedTab === "api-key" && <ApiKeyContent />}
					{selectedTab === "prompts" && <PromptsContent />}
					{selectedTab === "community-prompts" && <CommunityPromptsContent />}
					{selectedTab === "memory" && <MemoryContent />}
					{selectedTab === "agent-permissions" && <AgentPermissionsContent />}
					{selectedTab === "agent-status" && <AgentStatusContent />}
					{selectedTab === "purchases" && <PurchaseHistoryContent />}
					{selectedTab === "desktop" && <DesktopContent />}
					{selectedTab === "desktop-shortcuts" && <DesktopShortcutsContent />}
				</div>
			</div>
		</section>
	);
}
