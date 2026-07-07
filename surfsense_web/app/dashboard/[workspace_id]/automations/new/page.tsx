import { AutomationNewContent } from "./automation-new-content";

export default async function NewAutomationPage({
	params,
}: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = await params;

	return (
		<div className="w-full space-y-6">
			<AutomationNewContent workspaceId={Number(workspace_id)} />
		</div>
	);
}
