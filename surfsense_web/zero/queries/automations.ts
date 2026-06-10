import { defineQuery } from "@rocicorp/zero";
import { z } from "zod";
import { zql } from "../schema/index";

// Mirrors chat byThread: client passes the parent id, the REST route still
// authorizes via `automation_id -> search_space`. No search_space_id on the
// table by design.
export const automationRunQueries = {
	byAutomation: defineQuery(z.object({ automationId: z.number() }), ({ args: { automationId } }) =>
		zql.automation_runs.where("automationId", automationId).orderBy("createdAt", "desc")
	),
};
