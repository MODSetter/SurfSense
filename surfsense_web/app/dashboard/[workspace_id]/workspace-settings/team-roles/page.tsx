import { RolesManager } from "@/components/settings/roles-manager";

export default async function Page({ params }: { params: Promise<{ workspace_id: string }> }) {
	const { workspace_id } = await params;
	return <RolesManager workspaceId={Number(workspace_id)} />;
}
