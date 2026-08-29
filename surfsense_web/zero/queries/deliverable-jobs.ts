import { defineQuery } from "@rocicorp/zero";
import { z } from "zod";
import { zql } from "../schema/index";
import { canReadSpace, constrainToAllowedSpaces, denySpace } from "./authz";

export const deliverableJobQueries = {
	bySpace: defineQuery(z.object({ workspaceId: z.number() }), ({ args: { workspaceId }, ctx }) => {
		const query = zql.deliverable_jobs.where("workspaceId", workspaceId);
		if (!canReadSpace(ctx, workspaceId)) return denySpace(query).orderBy("createdAt", "desc");
		return constrainToAllowedSpaces(query, ctx).orderBy("createdAt", "desc");
	}),
	byId: defineQuery(z.object({ jobId: z.number() }), ({ args: { jobId }, ctx }) =>
		constrainToAllowedSpaces(zql.deliverable_jobs.where("id", jobId), ctx).one()
	),
};
