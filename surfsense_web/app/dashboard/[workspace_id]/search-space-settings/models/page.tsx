import { ModelConnectionsSettings } from "@/components/settings/model-connections-settings";

export default async function Page({ params }: { params: Promise<{ workspace_id: string }> }) {
	const { workspace_id } = await params;
	return <ModelConnectionsSettings workspaceId={Number(workspace_id)} />;
}
