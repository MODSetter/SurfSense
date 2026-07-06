import { redirect } from "next/navigation";

export default async function SearchSpaceSettingsPage({
	params,
}: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = await params;
	redirect(`/dashboard/${workspace_id}/search-space-settings/general`);
}
