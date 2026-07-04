import { TeamContent } from "./team-content";

export default async function TeamPage({
	params,
}: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = await params;

	return (
		<div className="w-full select-none space-y-6">
			<TeamContent workspaceId={Number(workspace_id)} />
		</div>
	);
}
