import { ApiKeysSection } from "../components/api-keys-section";

export default async function PlaygroundApiKeysPage({
	params,
}: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = await params;

	return (
		<div className="mx-auto w-full max-w-3xl">
			<ApiKeysSection workspaceId={Number(workspace_id)} />
		</div>
	);
}
