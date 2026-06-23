import { defineQuery } from "@rocicorp/zero";
import { z } from "zod";
import { zql } from "../schema/index";
import { canReadSpace, constrainToAllowedSpaces, denySpace } from "./authz";

export const podcastQueries = {
	bySpace: defineQuery(z.object({ searchSpaceId: z.number() }), ({ args: { searchSpaceId }, ctx }) => {
		const query = zql.podcasts.where("searchSpaceId", searchSpaceId);
		if (!canReadSpace(ctx, searchSpaceId)) return denySpace(query).orderBy("createdAt", "desc");
		return constrainToAllowedSpaces(query, ctx).orderBy("createdAt", "desc");
	}),
	byId: defineQuery(z.object({ podcastId: z.number() }), ({ args: { podcastId }, ctx }) =>
		constrainToAllowedSpaces(zql.podcasts.where("id", podcastId), ctx).one()
	),
};
