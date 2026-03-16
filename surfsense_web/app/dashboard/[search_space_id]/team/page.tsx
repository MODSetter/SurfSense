"use client";

import { useParams } from "next/navigation";
import { TeamContent } from "./team-content";

export default function TeamManagementPage() {
	const params = useParams();
	const searchSpaceId = Number(params.search_space_id);

	return (
		<div className="bg-background select-none">
			<div className="container max-w-5xl mx-auto p-4 md:p-6 lg:p-8 pt-20 md:pt-24 lg:pt-28">
				<TeamContent searchSpaceId={searchSpaceId} />
			</div>
		</div>
	);
}
