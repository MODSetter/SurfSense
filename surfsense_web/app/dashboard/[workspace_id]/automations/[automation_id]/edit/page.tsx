import { AutomationEditContent } from "./automation-edit-content";

export default async function AutomationEditPage({
	params,
}: {
	params: Promise<{ workspace_id: string; automation_id: string }>;
}) {
	const { workspace_id, automation_id } = await params;

	return (
		<div className="w-full space-y-6">
			<AutomationEditContent
				workspaceId={Number(workspace_id)}
				automationId={Number(automation_id)}
			/>
		</div>
	);
}
