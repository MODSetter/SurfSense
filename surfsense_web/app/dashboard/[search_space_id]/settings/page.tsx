"use client";

import { Bot, Brain, FileText, Globe, ImageIcon, MessageSquare, Shield } from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect } from "react";
import { PublicChatSnapshotsManager } from "@/components/public-chat-snapshots/public-chat-snapshots-manager";
import { GeneralSettingsManager } from "@/components/settings/general-settings-manager";
import { ImageModelManager } from "@/components/settings/image-model-manager";
import { LLMRoleManager } from "@/components/settings/llm-role-manager";
import { ModelConfigManager } from "@/components/settings/model-config-manager";
import { PromptConfigManager } from "@/components/settings/prompt-config-manager";
import { RolesManager } from "@/components/settings/roles-manager";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/animated-tabs";
import { trackSettingsViewed } from "@/lib/posthog/events";

const VALID_TABS = [
	"general",
	"models",
	"roles",
	"image-models",
	"prompts",
	"public-links",
	"team-roles",
] as const;

const DEFAULT_TAB = "general";

export default function SettingsPage() {
	const t = useTranslations("searchSpaceSettings");
	const router = useRouter();
	const params = useParams();
	const searchParams = useSearchParams();
	const searchSpaceId = Number(params.search_space_id);

	const tabParam = searchParams.get("tab") ?? "";
	const activeTab = VALID_TABS.includes(tabParam as (typeof VALID_TABS)[number])
		? tabParam
		: DEFAULT_TAB;

	const handleTabChange = useCallback(
		(value: string) => {
			const p = new URLSearchParams(searchParams.toString());
			p.set("tab", value);
			router.replace(`?${p.toString()}`, { scroll: false });
		},
		[router, searchParams]
	);

	useEffect(() => {
		trackSettingsViewed(searchSpaceId, activeTab);
	}, [searchSpaceId, activeTab]);

	return (
		<div className="h-full overflow-y-auto">
			<div className="mx-auto w-full max-w-4xl px-4 py-10">
				<Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
					<TabsList showBottomBorder>
						<TabsTrigger value="general">
							<FileText className="mr-2 h-4 w-4" />
							{t("nav_general")}
						</TabsTrigger>
						<TabsTrigger value="models">
							<Bot className="mr-2 h-4 w-4" />
							{t("nav_agent_configs")}
						</TabsTrigger>
						<TabsTrigger value="roles">
							<Brain className="mr-2 h-4 w-4" />
							{t("nav_role_assignments")}
						</TabsTrigger>
						<TabsTrigger value="image-models">
							<ImageIcon className="mr-2 h-4 w-4" />
							{t("nav_image_models")}
						</TabsTrigger>
						<TabsTrigger value="team-roles">
							<Shield className="mr-2 h-4 w-4" />
							{t("nav_team_roles")}
						</TabsTrigger>
					<TabsTrigger value="prompts">
						<MessageSquare className="mr-2 h-4 w-4" />
						{t("nav_system_instructions")}
					</TabsTrigger>
					<TabsTrigger value="public-links">
						<Globe className="mr-2 h-4 w-4" />
						{t("nav_public_links")}
					</TabsTrigger>
				</TabsList>
					<TabsContent value="general" className="mt-6">
						<GeneralSettingsManager searchSpaceId={searchSpaceId} />
					</TabsContent>
					<TabsContent value="models" className="mt-6">
						<ModelConfigManager searchSpaceId={searchSpaceId} />
					</TabsContent>
					<TabsContent value="roles" className="mt-6">
						<LLMRoleManager searchSpaceId={searchSpaceId} />
					</TabsContent>
					<TabsContent value="image-models" className="mt-6">
						<ImageModelManager searchSpaceId={searchSpaceId} />
					</TabsContent>
					<TabsContent value="prompts" className="mt-6">
						<PromptConfigManager searchSpaceId={searchSpaceId} />
					</TabsContent>
					<TabsContent value="public-links" className="mt-6">
						<PublicChatSnapshotsManager searchSpaceId={searchSpaceId} />
					</TabsContent>
					<TabsContent value="team-roles" className="mt-6">
						<RolesManager searchSpaceId={searchSpaceId} />
					</TabsContent>
				</Tabs>
			</div>
		</div>
	);
}
