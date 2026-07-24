import { GeneralSettingsManager } from "@/components/settings/general-settings-manager";

export default async function Page({ params }: { params: Promise<{ workspace_id: string }> }) {
	const { workspace_id } = await params;
	return <GeneralSettingsManager workspaceId={Number(workspace_id)} />;
}
