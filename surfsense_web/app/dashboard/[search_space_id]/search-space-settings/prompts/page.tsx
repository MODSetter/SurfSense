import { PromptConfigManager } from "@/components/settings/prompt-config-manager";

export default async function Page({
	params,
}: {
	params: Promise<{ search_space_id: string }>;
}) {
	const { search_space_id } = await params;
	return <PromptConfigManager searchSpaceId={Number(search_space_id)} />;
}
