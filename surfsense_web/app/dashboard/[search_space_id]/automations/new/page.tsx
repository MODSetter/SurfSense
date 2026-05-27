import { AutomationNewContent } from "./automation-new-content";

export default async function NewAutomationPage({
	params,
}: {
	params: Promise<{ search_space_id: string }>;
}) {
	const { search_space_id } = await params;

	return (
		<div className="w-full space-y-6">
			<AutomationNewContent searchSpaceId={Number(search_space_id)} />
		</div>
	);
}
