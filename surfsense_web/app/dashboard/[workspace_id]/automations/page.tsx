import { AutomationsContent } from "./automations-content";

export default async function AutomationsPage({
	params,
}: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = await params;

	return (
		<div className="mx-auto w-full max-w-5xl space-y-6">
			<AutomationsContent workspaceId={Number(workspace_id)} />
		</div>
	);
}
