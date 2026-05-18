import { RolesManager } from "@/components/settings/roles-manager";

export default async function Page({
	params,
}: {
	params: Promise<{ search_space_id: string }>;
}) {
	const { search_space_id } = await params;
	return <RolesManager searchSpaceId={Number(search_space_id)} />;
}
