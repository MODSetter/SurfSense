import { defineQuery } from "@rocicorp/zero";
import { z } from "zod";
import { zql } from "../schema/index";
import { canReadSpace, constrainToAllowedSpaces, denySpace } from "./authz";

export const folderQueries = {
	bySpace: defineQuery(z.object({ workspaceId: z.number() }), ({ args: { workspaceId }, ctx }) => {
		const query = zql.folders.where("workspaceId", workspaceId);
		if (!canReadSpace(ctx, workspaceId)) return denySpace(query).orderBy("position", "asc");
		return constrainToAllowedSpaces(query, ctx).orderBy("position", "asc");
	}),
};
