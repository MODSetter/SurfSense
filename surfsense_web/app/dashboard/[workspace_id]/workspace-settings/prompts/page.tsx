import { PromptConfigManager } from "@/components/settings/prompt-config-manager";

export default async function Page({ params }: { params: Promise<{ workspace_id: string }> }) {
	const { workspace_id } = await params;
	return <PromptConfigManager workspaceId={Number(workspace_id)} />;
}
