import { GitRemoteSettings } from "@/components/settings/git-remote-settings";

export default async function Page({
	params,
	searchParams,
}: {
	params: Promise<{ workspace_id: string }>;
	searchParams: Promise<{
		github_installation_id?: string;
		github_installations?: string;
		github_error?: string;
	}>;
}) {
	const { workspace_id } = await params;
	const { github_installation_id, github_installations, github_error } = await searchParams;
	return (
		<GitRemoteSettings
			workspaceId={Number(workspace_id)}
			githubInstallationId={github_installation_id}
			githubInstallations={github_installations}
			githubError={github_error}
		/>
	);
}
