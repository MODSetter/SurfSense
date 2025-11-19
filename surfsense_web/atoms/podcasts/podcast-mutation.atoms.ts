import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import { activeSearchSpaceIdAtom } from "@/atoms/seach-spaces/seach-space-queries.atom";
import type { DeletePodcastRequest, Podcast } from "@/contracts/types/podcast.types";
import { podcastsApiService } from "@/lib/apis/podcasts-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";

export const deletePodcastMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	const authToken = localStorage.getItem("surfsense_bearer_token");

	return {
		mutationKey: cacheKeys.podcasts(),
		enabled: !!searchSpaceId && !!authToken,
		mutationFn: async (request: DeletePodcastRequest) => {
			return podcastsApiService.deletePodcast(request);
		},

		onSuccess: (_, request: DeletePodcastRequest) => {
			toast.success("Podcast deleted successfully");
			queryClient.setQueryData(cacheKeys.podcasts(), (oldData: Podcast[]) => {
				return oldData.filter((podcast) => podcast.id !== request.id);
			});
		},
	};
});
