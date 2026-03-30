"use client";

import { useAtom } from "jotai";
import { Globe, KeyRound, Sparkles, User } from "lucide-react";
import { useTranslations } from "next-intl";
import { ApiKeyContent } from "@/app/dashboard/[search_space_id]/user-settings/components/ApiKeyContent";
import { CommunityPromptsContent } from "@/app/dashboard/[search_space_id]/user-settings/components/CommunityPromptsContent";
import { ProfileContent } from "@/app/dashboard/[search_space_id]/user-settings/components/ProfileContent";
import { PromptsContent } from "@/app/dashboard/[search_space_id]/user-settings/components/PromptsContent";
import { userSettingsDialogAtom } from "@/atoms/settings/settings-dialog.atoms";
import { SettingsDialog } from "@/components/settings/settings-dialog";

export function UserSettingsDialog() {
	const t = useTranslations("userSettings");
	const [state, setState] = useAtom(userSettingsDialogAtom);

	const navItems = [
		{ value: "profile", label: t("profile_nav_label"), icon: <User className="h-4 w-4" /> },
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
	];

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
			</div>
		</SettingsDialog>
	);
}
