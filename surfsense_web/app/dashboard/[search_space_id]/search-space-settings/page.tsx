import { redirect } from "next/navigation";

export default async function SearchSpaceSettingsPage({
	params,
}: {
	params: Promise<{ search_space_id: string }>;
}) {
	const { search_space_id } = await params;
	redirect(`/dashboard/${search_space_id}/search-space-settings/general`);
}
