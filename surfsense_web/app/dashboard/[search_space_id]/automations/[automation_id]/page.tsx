import { AutomationDetailContent } from "./automation-detail-content";

export default async function AutomationDetailPage({
	params,
}: {
	params: Promise<{ search_space_id: string; automation_id: string }>;
}) {
	const { search_space_id, automation_id } = await params;

	return (
		<div className="w-full space-y-6">
			<AutomationDetailContent
				searchSpaceId={Number(search_space_id)}
				automationId={Number(automation_id)}
			/>
		</div>
	);
}
