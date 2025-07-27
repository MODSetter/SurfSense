import { Suspense } from "react";
import PodcastsPageClient from "./podcasts-client";

interface PageProps {
	params: {
		search_space_id: string;
	};
}

export default async function PodcastsPage({ params }: PageProps) {
	const { search_space_id: searchSpaceId } = await Promise.resolve(params);

	return (
		<Suspense
			fallback={
				<div className="flex items-center justify-center h-[60vh]">
					<div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
				</div>
			}
		>
			<PodcastsPageClient searchSpaceId={searchSpaceId} />
		</Suspense>
	);
}
