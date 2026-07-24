"use client";

import { BookText, Cpu, Earth, Settings, UserKey } from "lucide-react";
import { useSelectedLayoutSegment } from "next/navigation";
import { useTranslations } from "next-intl";
import type React from "react";
import { useMemo } from "react";
import { type RoutedSectionItem, RoutedSectionShell } from "@/components/layout";

export type WorkspaceSettingsTab = "general" | "models" | "team-roles" | "prompts" | "public-links";

const DEFAULT_TAB: WorkspaceSettingsTab = "general";

interface WorkspaceSettingsLayoutShellProps {
	workspaceId: string;
	children: React.ReactNode;
}

export function WorkspaceSettingsLayoutShell({
	workspaceId,
	children,
}: WorkspaceSettingsLayoutShellProps) {
	const t = useTranslations("workspaceSettings");
	const segment = useSelectedLayoutSegment();

	const navItems = useMemo<RoutedSectionItem[]>(
		() => [
			{
				value: "general" as const,
				label: t("nav_general"),
				href: `/dashboard/${workspaceId}/workspace-settings/general`,
				icon: <Settings className="h-4 w-4" />,
			},
			{
				value: "models" as const,
				label: t("nav_models"),
				href: `/dashboard/${workspaceId}/workspace-settings/models`,
				icon: <Cpu className="h-4 w-4" />,
			},
			{
				value: "team-roles" as const,
				label: t("nav_team_roles"),
				href: `/dashboard/${workspaceId}/workspace-settings/team-roles`,
				icon: <UserKey className="h-4 w-4" />,
			},
			{
				value: "prompts" as const,
				label: t("nav_system_instructions"),
				href: `/dashboard/${workspaceId}/workspace-settings/prompts`,
				icon: <BookText className="h-4 w-4" />,
			},
			{
				value: "public-links" as const,
				label: t("nav_public_links"),
				href: `/dashboard/${workspaceId}/workspace-settings/public-links`,
				icon: <Earth className="h-4 w-4" />,
			},
		],
		[t, workspaceId]
	);

	const activeTab: WorkspaceSettingsTab =
		segment && navItems.some((item) => item.value === segment)
			? (segment as WorkspaceSettingsTab)
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
