import { GeneralSettingsManager } from "@/components/settings/general-settings-manager";

export default async function Page({ params }: { params: Promise<{ search_space_id: string }> }) {
	const { search_space_id } = await params;
	return <GeneralSettingsManager searchSpaceId={Number(search_space_id)} />;
}
