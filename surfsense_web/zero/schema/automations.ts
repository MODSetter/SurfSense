import { json, number, string, table } from "@rocicorp/zero";

export const automationTable = table("automations")
	.columns({
		id: number(),
		searchSpaceId: number().from("workspace_id"),
	})
	.primaryKey("id");

// Thin live row: status + per-step progress only. Heavy fields
// (definition_snapshot, inputs, output, artifacts, error) stay on REST
// (`GET /automations/{id}/runs/{run_id}`) and load on detail expand.
// Mirrors the publication shape in migration 148.
export const automationRunTable = table("automation_runs")
	.columns({
		id: number(),
		automationId: number().from("automation_id"),
		triggerId: number().optional().from("trigger_id"),
		status: string(),
		stepResults: json().from("step_results"),
		startedAt: number().optional().from("started_at"),
		finishedAt: number().optional().from("finished_at"),
		createdAt: number().from("created_at"),
	})
	.primaryKey("id");
