import { AgentModelManager } from "@/components/settings/agent-model-manager";

export default async function Page({
	params,
}: {
	params: Promise<{ search_space_id: string }>;
}) {
	const { search_space_id } = await params;
	return <AgentModelManager searchSpaceId={Number(search_space_id)} />;
}
