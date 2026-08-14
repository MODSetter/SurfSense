"use client";

import { useQuery as useZeroQuery } from "@rocicorp/zero/react";
import { useMemo } from "react";
import { queries } from "@/zero/queries";
import type { LibraryArtifact, LibraryArtifactStatus } from "../model/artifact";

function runStatus(status: string): LibraryArtifactStatus {
	if (status === "failed" || status === "cancelled") return "error";
	return "running";
}

interface ZeroPodcastRunRow {
	id: number;
	title: string;
	status: string;
	artifactId?: number | null;
	workspaceId: number;
	threadId?: number | null;
	createdAt: number;
}

/**
 * In-flight and failed podcast runs, sourced from Zero by push. A delivered run
 * ("ready") is already represented by its Artifact row, so it is filtered out
 * here to avoid a duplicate card.
 */
export function useLibraryPodcastRuns(workspaceId: number): LibraryArtifact[] {
	const [rows] = useZeroQuery(queries.podcastRuns.bySpace({ workspaceId }));

	return useMemo(
		() =>
			(rows as ZeroPodcastRunRow[])
				.filter((row) => row.status !== "ready")
				.map((row) => ({
					key: `podcast-run-${row.id}`,
					format: "podcast",
					artifactId: row.artifactId ?? undefined,
					title: row.title,
					status: runStatus(row.status),
					createdAt: new Date(row.createdAt).toISOString(),
					sourceThreadId: row.threadId ?? null,
				})),
		[rows]
	);
}
