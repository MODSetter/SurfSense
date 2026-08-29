import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
	DeliverableJobStatusCard,
	deliverableFailureMessage,
	deliverablePhaseLabel,
	EnqueueDeliverableJobToolUI,
} from "@/components/tool-ui/deliverable-job";
import { Mp4ArtifactCard } from "@/components/tool-ui/save-artifact";
import type { LiveDeliverableJob } from "@/hooks/use-deliverable-job-live";
import {
	deliverableJobActionPath,
	deliverableJobActionRequestOptions,
} from "@/lib/apis/deliverable-jobs-api.service";

function job(overrides: Partial<LiveDeliverableJob> = {}): LiveDeliverableJob {
	return {
		id: 42,
		kind: "video",
		title: "Quarterly update",
		status: "queued",
		phase: null,
		progress: 0,
		failureCode: null,
		artifactId: null,
		workspaceId: 7,
		threadId: 9,
		...overrides,
	};
}

function renderJob(overrides: Partial<LiveDeliverableJob>) {
	return renderToStaticMarkup(createElement(DeliverableJobStatusCard, { job: job(overrides) }));
}

test("enqueue bootstrap renders before the tool has a job result", () => {
	const card = EnqueueDeliverableJobToolUI({
		type: "tool-call",
		toolName: "enqueue_deliverable_job",
		argsText: '{"title":"Quarterly update","brief":"Make a short video"}',
		args: { title: "Quarterly update", brief: "Make a short video" },
		result: undefined,
		status: { type: "running" },
		toolCallId: "tool-1",
		addResult: () => {},
		resume: () => {},
		respondToApproval: () => {},
	});
	const html = renderToStaticMarkup(card);

	assert.match(html, /Starting video generation/);
	assert.match(html, /Quarterly update/);
});

test("successful nested result renders live card even when tool status is incomplete", () => {
	const card = EnqueueDeliverableJobToolUI({
		type: "tool-call",
		toolName: "enqueue_deliverable_job",
		argsText: '{"title":"Quarterly update","brief":"Make a short video"}',
		args: { title: "Quarterly update", brief: "Make a short video" },
		result: { status: "pending", job_id: 42, title: "Quarterly update" },
		status: { type: "incomplete", reason: "error" },
		toolCallId: "tool-1",
		addResult: () => {},
		resume: () => {},
		respondToApproval: () => {},
	});

	assert.equal(card.props.jobId, 42);
});

test("deliverable cards render queued, running, cancelling, cancelled, and failed states", () => {
	assert.match(renderJob({ status: "queued" }), /Generating your video/);
	const running = renderJob({ status: "running", phase: "rendering", progress: 72 });
	assert.match(running, /Rendering your video/);
	assert.doesNotMatch(running, /72%|progressbar/);
	assert.match(running, /w-full/);
	assert.doesNotMatch(running, /max-w-lg/);
	assert.match(running, /size-5 text-muted-foreground/);
	assert.match(running, /h-\[74px\]/);
	assert.match(running, /select-none/);
	assert.match(running, /w-16 shrink-0/);
	assert.match(renderJob({ status: "cancelling" }), /Cancelling video generation/);
	const cancelled = renderJob({ status: "cancelled" });
	assert.match(cancelled, /Retry/);
	assert.match(cancelled, /h-\[74px\]/);
	assert.match(cancelled, /w-16 shrink-0/);
	assert.match(
		renderJob({ status: "failed", failureCode: "render_failed" }),
		/could not be rendered/
	);
});

test("failure and phase copy never reflects unknown backend strings", () => {
	assert.equal(
		deliverableFailureMessage("postgres password leaked"),
		"Video generation failed. Please try again."
	);
	assert.equal(deliverablePhaseLabel("internal_worker_name"), "Generating your video");
});

test("cancel and retry controls use workspace-scoped routes", () => {
	assert.equal(
		deliverableJobActionPath(7, 42, "cancel"),
		"/api/v1/workspaces/7/deliverable-jobs/42/cancel"
	);
	assert.equal(
		deliverableJobActionPath(7, 42, "retry"),
		"/api/v1/workspaces/7/deliverable-jobs/42/retry"
	);
	assert.deepEqual(deliverableJobActionRequestOptions(false), { sameOrigin: true });
	assert.deepEqual(deliverableJobActionRequestOptions(true), { sameOrigin: false });
	assert.match(renderJob({ status: "queued" }), /Cancel/);
	assert.match(renderJob({ status: "failed" }), /Retry/);
});

test("ready jobs hand off to the shared MP4 artifact card", () => {
	const ready = DeliverableJobStatusCard({ job: job({ status: "ready", artifactId: 81 }) });
	assert.equal(ready.type, Mp4ArtifactCard);
	assert.equal(ready.props.artifactId, 81);

	assert.match(renderJob({ status: "ready", artifactId: null }), /it is not available yet/);
});
