"use client";

import { useAtom } from "jotai";
import { Bot, Brain, Eye, FileText, Globe, ImageIcon, MessageSquare, Shield } from "lucide-react";
import { useTranslations } from "next-intl";
import type React from "react";
import { searchSpaceSettingsDialogAtom } from "@/atoms/settings/settings-dialog.atoms";
import { PublicChatSnapshotsManager } from "@/components/public-chat-snapshots/public-chat-snapshots-manager";
import { GeneralSettingsManager } from "@/components/settings/general-settings-manager";
import { ImageModelManager } from "@/components/settings/image-model-manager";
import { LLMRoleManager } from "@/components/settings/llm-role-manager";
import { ModelConfigManager } from "@/components/settings/model-config-manager";
import { PromptConfigManager } from "@/components/settings/prompt-config-manager";
import { RolesManager } from "@/components/settings/roles-manager";
import { SettingsDialog } from "@/components/settings/settings-dialog";
import { VisionModelManager } from "@/components/settings/vision-model-manager";

interface SearchSpaceSettingsDialogProps {
	searchSpaceId: number;
}

export function SearchSpaceSettingsDialog({ searchSpaceId }: SearchSpaceSettingsDialogProps) {
	const t = useTranslations("searchSpaceSettings");
	const [state, setState] = useAtom(searchSpaceSettingsDialogAtom);

	const navItems = [
		{ value: "general", label: t("nav_general"), icon: <FileText className="h-4 w-4" /> },
		{ value: "models", label: t("nav_agent_configs"), icon: <Bot className="h-4 w-4" /> },
		{ value: "roles", label: t("nav_role_assignments"), icon: <Brain className="h-4 w-4" /> },
		{
			value: "image-models",
			label: t("nav_image_models"),
			icon: <ImageIcon className="h-4 w-4" />,
		},
		{
			value: "vision-models",
			label: t("nav_vision_models"),
			icon: <Eye className="h-4 w-4" />,
		},
		{ value: "team-roles", label: t("nav_team_roles"), icon: <Shield className="h-4 w-4" /> },
		{
			value: "prompts",
			label: t("nav_system_instructions"),
			icon: <MessageSquare className="h-4 w-4" />,
		},
		{ value: "public-links", label: t("nav_public_links"), icon: <Globe className="h-4 w-4" /> },
	];

	const content: Record<string, React.ReactNode> = {
		general: <GeneralSettingsManager searchSpaceId={searchSpaceId} />,
		models: <ModelConfigManager searchSpaceId={searchSpaceId} />,
		roles: <LLMRoleManager searchSpaceId={searchSpaceId} />,
		"image-models": <ImageModelManager searchSpaceId={searchSpaceId} />,
		"vision-models": <VisionModelManager searchSpaceId={searchSpaceId} />,
		"team-roles": <RolesManager searchSpaceId={searchSpaceId} />,
		prompts: <PromptConfigManager searchSpaceId={searchSpaceId} />,
		"public-links": <PublicChatSnapshotsManager searchSpaceId={searchSpaceId} />,
	};

	return (
		<SettingsDialog
			open={state.open}
			onOpenChange={(open) => setState((prev) => ({ ...prev, open }))}
			title={t("title")}
			navItems={navItems}
			activeItem={state.initialTab}
			onItemChange={(tab) => setState((prev) => ({ ...prev, initialTab: tab }))}
		>
			<div className="pt-4">{content[state.initialTab]}</div>
		</SettingsDialog>
	);
}
