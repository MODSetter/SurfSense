import { PlaygroundRunner } from "../../components/playground-runner";

export default async function PlaygroundVerbPage({
	params,
}: {
	params: Promise<{ workspace_id: string; platform: string; verb: string }>;
}) {
	const { workspace_id, platform, verb } = await params;

	return (
		<div className="mx-auto w-full max-w-6xl">
			<PlaygroundRunner workspaceId={Number(workspace_id)} platform={platform} verb={verb} />
		</div>
	);
}
