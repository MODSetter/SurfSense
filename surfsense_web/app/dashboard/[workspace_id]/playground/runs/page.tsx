import { RunsTable } from "../components/runs-table";

export default async function PlaygroundRunsPage({
	params,
}: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = await params;

	return (
		<div className="mx-auto w-full max-w-6xl">
			<RunsTable workspaceId={Number(workspace_id)} />
		</div>
	);
}
