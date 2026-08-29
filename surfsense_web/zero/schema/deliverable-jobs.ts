import { number, string, table } from "@rocicorp/zero";

// Mirrors DELIVERABLE_JOB_COLS in the backend publication. Requests,
// checkpoints, internal errors, worker identities, and billing data are
// deliberately excluded from Zero.
export const deliverableJobTable = table("deliverable_jobs")
	.columns({
		id: number(),
		kind: string(),
		title: string(),
		status: string(),
		phase: string().optional(),
		progress: number(),
		failureCode: string().optional().from("failure_code"),
		artifactId: number().optional().from("artifact_id"),
		workspaceId: number().from("workspace_id"),
		threadId: number().optional().from("thread_id"),
		createdAt: number().from("created_at"),
		updatedAt: number().from("updated_at"),
	})
	.primaryKey("id");
