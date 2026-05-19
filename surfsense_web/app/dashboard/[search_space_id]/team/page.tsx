import { TeamContent } from "./team-content";

export default async function TeamPage({
	params,
}: {
	params: Promise<{ search_space_id: string }>;
}) {
	const { search_space_id } = await params;

	return (
		<div className="w-full select-none space-y-6">
			<TeamContent searchSpaceId={Number(search_space_id)} />
		</div>
	);
}
