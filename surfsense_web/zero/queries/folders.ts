import { defineQuery } from "@rocicorp/zero";
import { z } from "zod";
import { zql } from "../schema/index";
import { canReadSpace, constrainToAllowedSpaces, denySpace } from "./authz";

export const folderQueries = {
	bySpace: defineQuery(
		z.object({ searchSpaceId: z.number() }),
		({ args: { searchSpaceId }, ctx }) => {
			const query = zql.folders.where("searchSpaceId", searchSpaceId);
			if (!canReadSpace(ctx, searchSpaceId)) return denySpace(query).orderBy("position", "asc");
			return constrainToAllowedSpaces(query, ctx).orderBy("position", "asc");
		}
	),
};
