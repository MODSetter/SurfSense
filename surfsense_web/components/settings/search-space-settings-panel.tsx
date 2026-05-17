"use client";

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
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type React from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

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

export type SearchSpaceSettingsTab =
	| "general"
	| "roles"
	| "models"
	| "image-models"
	| "vision-models"
	| "team-roles"
	| "prompts"
	| "team-memory"
	| "public-links";

interface SearchSpaceSettingsPanelProps {
	searchSpaceId: string;
	initialTab?: SearchSpaceSettingsTab;
}

export function SearchSpaceSettingsPanel({
	searchSpaceId,
	initialTab = "general",
}: SearchSpaceSettingsPanelProps) {
	const t = useTranslations("searchSpaceSettings");
	const router = useRouter();
	const numericSearchSpaceId = Number(searchSpaceId);
	const [activeTab, setActiveTab] = useState<SearchSpaceSettingsTab>(initialTab);
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
		],
		[t]
	);

	const selectedTab = navItems.some((item) => item.value === activeTab) ? activeTab : "general";
	const selectedLabel = navItems.find((item) => item.value === selectedTab)?.label ?? t("title");

	const handleItemChange = (tab: SearchSpaceSettingsTab) => {
		setActiveTab(tab);
		const suffix = tab === "general" ? "" : `?tab=${tab}`;
		router.replace(`/dashboard/${searchSpaceId}/search-space-settings${suffix}`, { scroll: false });
	};

	return (
		<section className="flex h-full min-h-[min(680px,calc(100vh-5rem))] w-full select-none flex-col gap-6 md:pt-6 md:flex-row">
			<div className="md:w-[220px] md:shrink-0">
				<h1 className="mb-4 px-1 text-2xl font-semibold tracking-tight">{t("title")}</h1>
				<nav className="hidden flex-col gap-0.5 md:flex">
					{navItems.map((item) => (
						<Button
							key={item.value}
							type="button"
							variant="ghost"
							onClick={() => handleItemChange(item.value as SearchSpaceSettingsTab)}
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
								onClick={() => handleItemChange(item.value as SearchSpaceSettingsTab)}
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
					<Separator className="mt-4" />
				</div>
				<div className="min-w-0 pt-4 md:max-w-3xl">
					{selectedTab === "general" && (
						<GeneralSettingsManager searchSpaceId={numericSearchSpaceId} />
					)}
					{selectedTab === "models" && <AgentModelManager searchSpaceId={numericSearchSpaceId} />}
					{selectedTab === "roles" && (
						<LLMRoleManager key={searchSpaceId} searchSpaceId={numericSearchSpaceId} />
					)}
					{selectedTab === "image-models" && (
						<ImageModelManager searchSpaceId={numericSearchSpaceId} />
					)}
					{selectedTab === "vision-models" && (
						<VisionModelManager searchSpaceId={numericSearchSpaceId} />
					)}
					{selectedTab === "team-roles" && <RolesManager searchSpaceId={numericSearchSpaceId} />}
					{selectedTab === "prompts" && (
						<PromptConfigManager searchSpaceId={numericSearchSpaceId} />
					)}
					{selectedTab === "team-memory" && (
						<TeamMemoryManager searchSpaceId={numericSearchSpaceId} />
					)}
					{selectedTab === "public-links" && (
						<PublicChatSnapshotsManager searchSpaceId={numericSearchSpaceId} />
					)}
				</div>
			</div>
		</section>
	);
}
