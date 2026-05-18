import { PublicChatSnapshotsManager } from "@/components/public-chat-snapshots/public-chat-snapshots-manager";

export default async function Page({
	params,
}: {
	params: Promise<{ search_space_id: string }>;
}) {
	const { search_space_id } = await params;
	return <PublicChatSnapshotsManager searchSpaceId={Number(search_space_id)} />;
}
