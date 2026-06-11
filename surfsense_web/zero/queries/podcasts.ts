import { defineQuery } from "@rocicorp/zero";
import { z } from "zod";
import { zql } from "../schema/index";

export const podcastQueries = {
	bySpace: defineQuery(z.object({ searchSpaceId: z.number() }), ({ args: { searchSpaceId } }) =>
		zql.podcasts.where("searchSpaceId", searchSpaceId).orderBy("createdAt", "desc")
	),
	byId: defineQuery(z.object({ podcastId: z.number() }), ({ args: { podcastId } }) =>
		zql.podcasts.where("id", podcastId).one()
	),
};
