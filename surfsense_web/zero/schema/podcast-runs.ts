import { json, number, string, table } from "@rocicorp/zero";

// Mirrors PODCAST_COLS in the backend zero_publication. status drives the
// lifecycle UI by push; spec is the reviewable brief. The bulky source_content
// and transcript are intentionally not published and are fetched over REST.
export const podcastRunTable = table("podcast_runs")
	.columns({
		id: number(),
		title: string(),
		status: string(),
		spec: json().optional(),
		specVersion: number().from("spec_version"),
		durationSeconds: number().optional().from("duration_seconds"),
		error: string().optional(),
		artifactId: number().optional().from("artifact_id"),
		workspaceId: number().from("workspace_id"),
		threadId: number().optional().from("thread_id"),
		createdAt: number().from("created_at"),
	})
	.primaryKey("id");
