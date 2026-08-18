import { defineQuery } from "@rocicorp/zero";
import { z } from "zod";
import { zql } from "../schema/index";
import { canReadSpace, constrainToAllowedSpaces, denySpace } from "./authz";

export const videoPresentationRunQueries = {
	bySpace: defineQuery(z.object({ workspaceId: z.number() }), ({ args: { workspaceId }, ctx }) => {
		const query = zql.video_presentation_runs.where("workspaceId", workspaceId);
		if (!canReadSpace(ctx, workspaceId)) return denySpace(query).orderBy("createdAt", "desc");
		return constrainToAllowedSpaces(query, ctx).orderBy("createdAt", "desc");
	}),
	byId: defineQuery(z.object({ runId: z.number() }), ({ args: { runId }, ctx }) =>
		constrainToAllowedSpaces(zql.video_presentation_runs.where("id", runId), ctx).one()
	),
};
