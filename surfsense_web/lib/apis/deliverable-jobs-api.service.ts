import { z } from "zod";
import { baseApiService } from "./base-api.service";

export const deliverableJobResponse = z.object({
	id: z.number(),
	kind: z.string(),
	title: z.string(),
	status: z.enum(["queued", "running", "cancelling", "cancelled", "failed", "ready"]),
	phase: z.string().nullish(),
	progress: z.number().min(0).max(100),
	failure_code: z.string().nullish(),
	artifact_id: z.number().nullish(),
	workspace_id: z.number(),
	thread_id: z.number().nullish(),
	created_at: z.string(),
	updated_at: z.string(),
});

export const deliverableJobActionPath = (
	workspaceId: number,
	jobId: number,
	action: "cancel" | "retry"
) => `/api/v1/workspaces/${workspaceId}/deliverable-jobs/${jobId}/${action}`;

export const deliverableJobActionRequestOptions = (isDesktopClient: boolean) => ({
	sameOrigin: !isDesktopClient,
});

class DeliverableJobsApiService {
	private postAction(workspaceId: number, jobId: number, action: "cancel" | "retry") {
		return baseApiService.post(
			deliverableJobActionPath(workspaceId, jobId, action),
			deliverableJobResponse,
			deliverableJobActionRequestOptions(baseApiService.isDesktopClient)
		);
	}

	cancel = (workspaceId: number, jobId: number) => this.postAction(workspaceId, jobId, "cancel");

	retry = (workspaceId: number, jobId: number) => this.postAction(workspaceId, jobId, "retry");
}

export const deliverableJobsApiService = new DeliverableJobsApiService();
