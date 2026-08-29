"use client";

import { useQuery as useZeroQuery } from "@rocicorp/zero/react";
import { useMemo } from "react";
import { queries } from "@/zero/queries";
import type { LibraryArtifact } from "../model/artifact";

interface ZeroDeliverableJobRow {
	id: number;
	kind: string;
	title: string;
	status: string;
	artifactId?: number | null;
	threadId?: number | null;
	createdAt: number;
}

const IN_FLIGHT = new Set(["queued", "running", "cancelling"]);

/** Active durable jobs only; ready videos are represented by Artifact rows. */
export function useLibraryDeliverableJobs(workspaceId: number): LibraryArtifact[] {
	const [rows] = useZeroQuery(queries.deliverableJobs.bySpace({ workspaceId }));

	return useMemo(
		() =>
			(rows as ZeroDeliverableJobRow[])
				.filter((row) => row.kind === "video" && IN_FLIGHT.has(row.status))
				.map((row) => ({
					key: `deliverable-job-${row.id}`,
					format: "video",
					artifactId: row.artifactId ?? undefined,
					title: row.title,
					status: "running" as const,
					createdAt: new Date(row.createdAt).toISOString(),
					sourceThreadId: row.threadId ?? null,
				})),
		[rows]
	);
}
