import { AutomationEditContent } from "./automation-edit-content";

export default async function AutomationEditPage({
	params,
}: {
	params: Promise<{ search_space_id: string; automation_id: string }>;
}) {
	const { search_space_id, automation_id } = await params;

	return (
		<div className="w-full space-y-6">
			<AutomationEditContent
				searchSpaceId={Number(search_space_id)}
				automationId={Number(automation_id)}
			/>
		</div>
	);
}
