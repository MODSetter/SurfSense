"use client";

import { useAtom } from "jotai";
import { Brain, CircleUser, Globe, Keyboard, KeyRound, Monitor, ReceiptText, Sparkles } from "lucide-react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { useMemo } from "react";
import { userSettingsDialogAtom } from "@/atoms/settings/settings-dialog.atoms";
import { SettingsDialog } from "@/components/settings/settings-dialog";
import { usePlatform } from "@/hooks/use-platform";

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
		import("@/app/dashboard/[search_space_id]/user-settings/components/DesktopShortcutsContent").then(
			(m) => ({ default: m.DesktopShortcutsContent })
		),
	{ ssr: false }
);
const MemoryContent = dynamic(
	() =>
		import("@/app/dashboard/[search_space_id]/user-settings/components/MemoryContent").then(
			(m) => ({ default: m.MemoryContent })
		),
	{ ssr: false }
);

export function UserSettingsDialog() {
	const t = useTranslations("userSettings");
	const [state, setState] = useAtom(userSettingsDialogAtom);
	const { isDesktop } = usePlatform();

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
				value: "purchases",
				label: "Purchase History",
				icon: <ReceiptText className="h-4 w-4" />,
			},
			...(isDesktop
				? [
						{
							value: "desktop",
							label: "App Preferences",
							icon: <Monitor className="h-4 w-4" />,
						},
						{
							value: "desktop-shortcuts",
							label: "Hotkeys",
							icon: <Keyboard className="h-4 w-4" />,
						},
					]
				: []),
		],
		[t, isDesktop]
	);

	return (
		<SettingsDialog
			open={state.open}
			onOpenChange={(open) => setState((prev) => ({ ...prev, open }))}
			title={t("title")}
			navItems={navItems}
			activeItem={state.initialTab}
			onItemChange={(tab) => setState((prev) => ({ ...prev, initialTab: tab }))}
		>
			<div className="pt-4">
				{state.initialTab === "profile" && <ProfileContent />}
				{state.initialTab === "api-key" && <ApiKeyContent />}
				{state.initialTab === "prompts" && <PromptsContent />}
				{state.initialTab === "community-prompts" && <CommunityPromptsContent />}
				{state.initialTab === "memory" && <MemoryContent />}
				{state.initialTab === "purchases" && <PurchaseHistoryContent />}
				{state.initialTab === "desktop" && <DesktopContent />}
				{state.initialTab === "desktop-shortcuts" && <DesktopShortcutsContent />}
			</div>
		</SettingsDialog>
	);
}
