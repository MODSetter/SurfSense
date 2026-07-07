import { AutomationDetailContent } from "./automation-detail-content";

export default async function AutomationDetailPage({
	params,
}: {
	params: Promise<{ workspace_id: string; automation_id: string }>;
}) {
	const { workspace_id, automation_id } = await params;

	return (
		<div className="w-full space-y-6">
			<AutomationDetailContent
				workspaceId={Number(workspace_id)}
				automationId={Number(automation_id)}
			/>
		</div>
	);
}
