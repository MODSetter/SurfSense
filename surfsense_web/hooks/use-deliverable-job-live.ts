"use client";

import { useQuery } from "@rocicorp/zero/react";
import { useMemo } from "react";
import { queries } from "@/zero/queries";

export type DeliverableJobStatus =
	| "queued"
	| "running"
	| "cancelling"
	| "cancelled"
	| "failed"
	| "ready";

export interface LiveDeliverableJob {
	id: number;
	kind: string;
	title: string;
	status: DeliverableJobStatus;
	phase: string | null;
	progress: number;
	failureCode: string | null;
	artifactId: number | null;
	workspaceId: number;
	threadId: number | null;
}

export function useDeliverableJobLive(jobId: number | undefined) {
	const [row, result] = useQuery(queries.deliverableJobs.byId({ jobId: jobId ?? -1 }));

	const job = useMemo<LiveDeliverableJob | undefined>(() => {
		if (!jobId || !row) return undefined;
		return {
			id: row.id,
			kind: row.kind,
			title: row.title,
			status: row.status as DeliverableJobStatus,
			phase: row.phase ?? null,
			progress: row.progress,
			failureCode: row.failureCode ?? null,
			artifactId: row.artifactId ?? null,
			workspaceId: row.workspaceId,
			threadId: row.threadId ?? null,
		};
	}, [jobId, row]);

	return {
		job,
		isLoading: !!jobId && !row && result.type !== "complete",
	};
}
