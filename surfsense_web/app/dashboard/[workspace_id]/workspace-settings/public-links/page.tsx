import { PublicChatSnapshotsManager } from "@/components/public-chat-snapshots/public-chat-snapshots-manager";

export default async function Page({ params }: { params: Promise<{ workspace_id: string }> }) {
	const { workspace_id } = await params;
	return <PublicChatSnapshotsManager workspaceId={Number(workspace_id)} />;
}
