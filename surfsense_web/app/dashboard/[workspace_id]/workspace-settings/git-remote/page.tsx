import { GitRemoteSettings } from "@/components/settings/git-remote-settings";

export default async function Page({
	params,
	searchParams,
}: {
	params: Promise<{ workspace_id: string }>;
	searchParams: Promise<{ github_installation_id?: string }>;
}) {
	const { workspace_id } = await params;
	const { github_installation_id } = await searchParams;
	return (
		<GitRemoteSettings
			workspaceId={Number(workspace_id)}
			githubInstallationId={github_installation_id}
		/>
	);
}
