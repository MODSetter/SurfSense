import { atom } from "jotai";
import type { GetPodcastsRequest } from "@/contracts/types/podcast.types";

export const globalPodcastsQueryParamsAtom = atom<GetPodcastsRequest["queryParams"]>({
	limit: 5,
	skip: 0,
});
