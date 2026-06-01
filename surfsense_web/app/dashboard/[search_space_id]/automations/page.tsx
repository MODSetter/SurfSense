import { AutomationsContent } from "./automations-content";

export default async function AutomationsPage({
	params,
}: {
	params: Promise<{ search_space_id: string }>;
}) {
	const { search_space_id } = await params;

	return (
		<div className="w-full space-y-6">
			<AutomationsContent searchSpaceId={Number(search_space_id)} />
		</div>
	);
}
