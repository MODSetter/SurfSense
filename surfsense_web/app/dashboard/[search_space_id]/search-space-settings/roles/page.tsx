import { LLMRoleManager } from "@/components/settings/llm-role-manager";

export default async function Page({ params }: { params: Promise<{ search_space_id: string }> }) {
	const { search_space_id } = await params;
	return <LLMRoleManager key={search_space_id} searchSpaceId={Number(search_space_id)} />;
}
