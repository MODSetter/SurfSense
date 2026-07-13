"use client";

import {
	CircleUser,
	Keyboard,
	KeyRound,
	Library,
	MessageCircle,
	Monitor,
	Palette,
	ReceiptText,
	ShieldCheck,
	WandSparkles,
} from "lucide-react";
import { useSelectedLayoutSegment } from "next/navigation";
import { useTranslations } from "next-intl";
import type React from "react";
import { useMemo } from "react";
import { type RoutedSectionItem, RoutedSectionShell } from "@/components/layout";
import { usePlatform } from "@/hooks/use-platform";

export type UserSettingsTab =
	| "profile"
	| "appearance"
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

	const navItems = useMemo<RoutedSectionItem[]>(
		() => [
			{
				value: "profile" as const,
				label: t("profile_nav_label"),
				href: `/dashboard/${workspaceId}/user-settings/profile`,
				icon: <CircleUser className="h-4 w-4" />,
			},
			{
				value: "appearance" as const,
				label: "Appearance",
				href: `/dashboard/${workspaceId}/user-settings/appearance`,
				icon: <Palette className="h-4 w-4" />,
			},
			{
				value: "api-key" as const,
				label: t("api_key_nav_label"),
				href: `/dashboard/${workspaceId}/user-settings/api-key`,
				icon: <KeyRound className="h-4 w-4" />,
			},
			{
				value: "prompts" as const,
				label: "My Prompts",
				href: `/dashboard/${workspaceId}/user-settings/prompts`,
				icon: <WandSparkles className="h-4 w-4" />,
			},
			{
				value: "community-prompts" as const,
				label: "Community Prompts",
				href: `/dashboard/${workspaceId}/user-settings/community-prompts`,
				icon: <Library className="h-4 w-4" />,
			},
			{
				value: "agent-permissions" as const,
				label: "Agent Permissions",
				href: `/dashboard/${workspaceId}/user-settings/agent-permissions`,
				icon: <ShieldCheck className="h-4 w-4" />,
			},
			{
				value: "messaging-channels" as const,
				label: "Messaging Channels",
				href: `/dashboard/${workspaceId}/user-settings/messaging-channels`,
				icon: <MessageCircle className="h-4 w-4" />,
			},
			{
				value: "purchases" as const,
				label: "Purchase History",
				href: `/dashboard/${workspaceId}/user-settings/purchases`,
				icon: <ReceiptText className="h-4 w-4" />,
			},
			...(isDesktop
				? [
						{
							value: "desktop" as const,
							label: "App Preferences",
							href: `/dashboard/${workspaceId}/user-settings/desktop`,
							icon: <Monitor className="h-4 w-4" />,
						},
						{
							value: "hotkeys" as const,
							label: "Hotkeys",
							href: `/dashboard/${workspaceId}/user-settings/hotkeys`,
							icon: <Keyboard className="h-4 w-4" />,
						},
					]
				: []),
		],
		[t, isDesktop, workspaceId]
	);

	const activeTab: UserSettingsTab =
		segment && navItems.some((item) => item.value === segment)
			? (segment as UserSettingsTab)
			: DEFAULT_TAB;
	const selectedLabel = navItems.find((item) => item.value === activeTab)?.label ?? t("title");

	return (
		<RoutedSectionShell
			title={t("title")}
			items={navItems}
			activeValue={activeTab}
			selectedLabel={selectedLabel}
			contentClassName="md:max-w-3xl"
		>
			{children}
		</RoutedSectionShell>
	);
}
