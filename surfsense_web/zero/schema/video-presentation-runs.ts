import { number, string, table } from "@rocicorp/zero";

// Mirrors VIDEO_PRESENTATION_RUN_COLS in the backend zero_publication. status
// and error drive the in-flight / failed UI by push; artifactId links the
// delivered result. The Remotion payload lives in the Artifact and is fetched
// over REST, never replicated here.
export const videoPresentationRunTable = table("video_presentation_runs")
	.columns({
		id: number(),
		title: string(),
		status: string(),
		error: string().optional(),
		artifactId: number().optional().from("artifact_id"),
		workspaceId: number().from("workspace_id"),
		threadId: number().optional().from("thread_id"),
		createdAt: number().from("created_at"),
	})
	.primaryKey("id");
