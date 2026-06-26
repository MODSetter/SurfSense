import { defineQuery } from "@rocicorp/zero";
import { z } from "zod";
import { zql } from "../schema/index";
import { canReadSpace, constrainToAllowedSpaces, denySpace } from "./authz";

export const documentQueries = {
	bySpace: defineQuery(
		z.object({ searchSpaceId: z.number() }),
		({ args: { searchSpaceId }, ctx }) => {
			const query = zql.documents.where("searchSpaceId", searchSpaceId);
			if (!canReadSpace(ctx, searchSpaceId)) return denySpace(query).orderBy("createdAt", "desc");
			return constrainToAllowedSpaces(query, ctx).orderBy("createdAt", "desc");
		}
	),
};

export const connectorQueries = {
	bySpace: defineQuery(
		z.object({ searchSpaceId: z.number() }),
		({ args: { searchSpaceId }, ctx }) => {
			const query = zql.search_source_connectors.where("searchSpaceId", searchSpaceId);
			if (!canReadSpace(ctx, searchSpaceId)) return denySpace(query).orderBy("createdAt", "desc");
			return constrainToAllowedSpaces(query, ctx).orderBy("createdAt", "desc");
		}
	),
};
