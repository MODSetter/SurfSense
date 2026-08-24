"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { type ReactNode, useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Mp4ArtifactCard } from "@/components/tool-ui/save-artifact";
import { Button } from "@/components/ui/button";
import { ArtifactFormatIcon } from "@/features/artifacts/artifact-format-icon";
import { type LiveDeliverableJob, useDeliverableJobLive } from "@/hooks/use-deliverable-job-live";
import { deliverableJobsApiService } from "@/lib/apis/deliverable-jobs-api.service";

const EnqueueDeliverableJobArgsSchema = z.object({
	title: z.string(),
	brief: z.string(),
	source_references: z.array(z.string()).nullish(),
	revision_artifact_id: z.number().nullish(),
});

const EnqueueDeliverableJobResultSchema = z.object({
	status: z.string(),
	job_id: z.number().nullish(),
	title: z.string().nullish(),
	message: z.string().nullish(),
	error: z.string().nullish(),
});

type EnqueueDeliverableJobArgs = z.infer<typeof EnqueueDeliverableJobArgsSchema>;
type EnqueueDeliverableJobResult = z.infer<typeof EnqueueDeliverableJobResultSchema>;

const FAILURE_MESSAGES: Record<string, string> = {
	duration_limit: "The requested video is too long to render. Shorten it and try again.",
	quota_exceeded: "Video generation capacity is unavailable for this request. Try again later.",
	generation_failed: "The video could not be generated. Please try again.",
	render_failed: "The video could not be rendered. Please try again.",
	verification_failed: "The rendered video did not pass verification. Please try again.",
	cancelled: "The video was cancelled.",
};

const PHASE_LABELS: Record<string, string> = {
	starting: "Generating your video",
	preparing: "Preparing your video",
	authoring: "Creating scenes",
	narrating: "Adding narration",
	preflighting: "Checking your video",
	reviewing: "Reviewing your video",
	repairing: "Improving scenes",
	rendering: "Rendering your video",
	verifying: "Finalizing your video",
	saving: "Saving your video",
};

export function deliverableFailureMessage(code: string | null): string {
	return (code && FAILURE_MESSAGES[code]) || "Video generation failed. Please try again.";
}

export function deliverablePhaseLabel(phase: string | null): string {
	return (phase && PHASE_LABELS[phase]) || "Generating your video";
}

function CardShell({
	title,
	children,
	action,
}: {
	title: string;
	children: ReactNode;
	action?: ReactNode;
}) {
	return (
		<div className="my-4 flex h-[74px] w-full select-none items-center gap-3 rounded-xl border bg-muted/30 p-4 text-left">
			<span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
				<ArtifactFormatIcon format="video" className="size-5 text-muted-foreground" />
			</span>
			<div className="min-w-0 flex-1" aria-live="polite">
				<p className="truncate text-sm font-medium text-foreground">{title}</p>
				<div className="mt-0.5 h-4 overflow-hidden leading-4 [&>*]:m-0 [&>*]:block [&>*]:truncate [&>*]:leading-4">
					{children}
				</div>
			</div>
			{action}
		</div>
	);
}

function ActionButton({ job, action }: { job: LiveDeliverableJob; action: "cancel" | "retry" }) {
	const [isPending, setIsPending] = useState(false);
	const retrying = action === "retry";

	const run = async () => {
		setIsPending(true);
		try {
			await deliverableJobsApiService[action](job.workspaceId, job.id);
			// Zero owns reconciliation; do not locally invent a lifecycle state.
		} catch (error) {
			toast.error(
				error instanceof Error
					? error.message
					: retrying
						? "Failed to retry the video"
						: "Failed to cancel the video"
			);
		} finally {
			setIsPending(false);
		}
	};

	return (
		<Button
			type="button"
			variant="ghost"
			size="sm"
			className="w-16 shrink-0 justify-center text-muted-foreground"
			disabled={isPending}
			onClick={run}
		>
			{retrying ? "Retry" : "Cancel"}
		</Button>
	);
}

export function DeliverableJobStatusCard({ job }: { job: LiveDeliverableJob }) {
	switch (job.status) {
		case "queued":
			return (
				<CardShell title={job.title} action={<ActionButton job={job} action="cancel" />}>
					<TextShimmerLoader text="Generating your video" size="sm" />
				</CardShell>
			);
		case "running":
			return (
				<CardShell title={job.title} action={<ActionButton job={job} action="cancel" />}>
					<TextShimmerLoader text={deliverablePhaseLabel(job.phase)} size="sm" />
				</CardShell>
			);
		case "cancelling":
			return (
				<CardShell title={job.title}>
					<TextShimmerLoader text="Cancelling video generation" size="sm" />
				</CardShell>
			);
		case "cancelled":
			return (
				<CardShell title={job.title} action={<ActionButton job={job} action="retry" />}>
					<p className="text-xs text-muted-foreground">Video generation was cancelled</p>
				</CardShell>
			);
		case "failed":
			return (
				<CardShell title={job.title} action={<ActionButton job={job} action="retry" />}>
					<p className="text-xs text-destructive">{deliverableFailureMessage(job.failureCode)}</p>
				</CardShell>
			);
		case "ready":
			if (job.artifactId == null) {
				return (
					<CardShell title={job.title}>
						<p className="text-xs text-muted-foreground">
							The video finished, but it is not available yet.
						</p>
					</CardShell>
				);
			}
			return (
				<Mp4ArtifactCard
					artifactId={job.artifactId}
					title={job.title}
					filename={`${job.title}.mp4`}
					workspaceId={job.workspaceId}
				/>
			);
		default:
			return (
				<CardShell title={job.title}>
					<p className="text-xs text-muted-foreground">Video status is unavailable.</p>
				</CardShell>
			);
	}
}

function LiveDeliverableJobCard({
	jobId,
	fallbackTitle,
}: {
	jobId: number;
	fallbackTitle: string;
}) {
	const { job, isLoading } = useDeliverableJobLive(jobId);
	if (job) return <DeliverableJobStatusCard job={job} />;
	return (
		<CardShell title={fallbackTitle}>
			{isLoading ? (
				<TextShimmerLoader text="Loading your video" size="sm" />
			) : (
				<p className="text-xs text-muted-foreground">
					This video is no longer available or you do not have access to it.
				</p>
			)}
		</CardShell>
	);
}

export const EnqueueDeliverableJobToolUI = ({
	args,
	result,
	status,
}: ToolCallMessagePartProps<EnqueueDeliverableJobArgs, EnqueueDeliverableJobResult>) => {
	const title = result?.title || args.title || "SurfSense Video";

	if (status.type === "running" || status.type === "requires-action" || !result) {
		return (
			<CardShell title={title}>
				<TextShimmerLoader text="Starting video generation" size="sm" />
			</CardShell>
		);
	}
	if (result.status === "failed" || !result.job_id) {
		return (
			<CardShell title={title}>
				<p className="text-xs text-destructive">
					Video generation could not start. Please try again.
				</p>
			</CardShell>
		);
	}
	return <LiveDeliverableJobCard jobId={result.job_id} fallbackTitle={title} />;
};
