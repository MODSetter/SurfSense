"use client";

import { useAtom } from "jotai";
import {
	BookText,
	Bot,
	Brain,
	CircleUser,
	Earth,
	ImageIcon,
	ListChecks,
	ScanEye,
	UserKey,
} from "lucide-react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import type React from "react";
import { searchSpaceSettingsDialogAtom } from "@/atoms/settings/settings-dialog.atoms";
import { SettingsDialog } from "@/components/settings/settings-dialog";

const GeneralSettingsManager = dynamic(
	() =>
		import("@/components/settings/general-settings-manager").then((m) => ({
			default: m.GeneralSettingsManager,
		})),
	{ ssr: false }
);
const AgentModelManager = dynamic(
	() =>
		import("@/components/settings/agent-model-manager").then((m) => ({
			default: m.AgentModelManager,
		})),
	{ ssr: false }
);
const LLMRoleManager = dynamic(
	() =>
		import("@/components/settings/llm-role-manager").then((m) => ({ default: m.LLMRoleManager })),
	{ ssr: false }
);
const ImageModelManager = dynamic(
	() =>
		import("@/components/settings/image-model-manager").then((m) => ({
			default: m.ImageModelManager,
		})),
	{ ssr: false }
);
const VisionModelManager = dynamic(
	() =>
		import("@/components/settings/vision-model-manager").then((m) => ({
			default: m.VisionModelManager,
		})),
	{ ssr: false }
);
const RolesManager = dynamic(
	() => import("@/components/settings/roles-manager").then((m) => ({ default: m.RolesManager })),
	{ ssr: false }
);
const PromptConfigManager = dynamic(
	() =>
		import("@/components/settings/prompt-config-manager").then((m) => ({
			default: m.PromptConfigManager,
		})),
	{ ssr: false }
);
const PublicChatSnapshotsManager = dynamic(
	() =>
		import("@/components/public-chat-snapshots/public-chat-snapshots-manager").then((m) => ({
			default: m.PublicChatSnapshotsManager,
		})),
	{ ssr: false }
);
const TeamMemoryManager = dynamic(
	() =>
		import("@/components/settings/team-memory-manager").then((m) => ({
			default: m.TeamMemoryManager,
		})),
	{ ssr: false }
);

interface SearchSpaceSettingsDialogProps {
	searchSpaceId: number;
}

export function SearchSpaceSettingsDialog({ searchSpaceId }: SearchSpaceSettingsDialogProps) {
	const t = useTranslations("searchSpaceSettings");
	const [state, setState] = useAtom(searchSpaceSettingsDialogAtom);

	const navItems = [
		{ value: "general", label: t("nav_general"), icon: <CircleUser className="h-4 w-4" /> },
		{ value: "roles", label: t("nav_role_assignments"), icon: <ListChecks className="h-4 w-4" /> },
		{ value: "models", label: t("nav_agent_models"), icon: <Bot className="h-4 w-4" /> },
		{
			value: "image-models",
			label: t("nav_image_models"),
			icon: <ImageIcon className="h-4 w-4" />,
		},
		{
			value: "vision-models",
			label: t("nav_vision_models"),
			icon: <ScanEye className="h-4 w-4" />,
		},
		{ value: "team-roles", label: t("nav_team_roles"), icon: <UserKey className="h-4 w-4" /> },
		{
			value: "prompts",
			label: t("nav_system_instructions"),
			icon: <BookText className="h-4 w-4" />,
		},
		{
			value: "team-memory",
			label: "Team Memory",
			icon: <Brain className="h-4 w-4" />,
		},
		{ value: "public-links", label: t("nav_public_links"), icon: <Earth className="h-4 w-4" /> },
	];

	const content: Record<string, React.ReactNode> = {
		general: <GeneralSettingsManager searchSpaceId={searchSpaceId} />,
		models: <AgentModelManager searchSpaceId={searchSpaceId} />,
		roles: <LLMRoleManager searchSpaceId={searchSpaceId} />,
		"image-models": <ImageModelManager searchSpaceId={searchSpaceId} />,
		"vision-models": <VisionModelManager searchSpaceId={searchSpaceId} />,
		"team-roles": <RolesManager searchSpaceId={searchSpaceId} />,
		prompts: <PromptConfigManager searchSpaceId={searchSpaceId} />,
		"team-memory": <TeamMemoryManager searchSpaceId={searchSpaceId} />,
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
