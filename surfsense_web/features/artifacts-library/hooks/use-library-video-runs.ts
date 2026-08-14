"use client";

import { useQuery as useZeroQuery } from "@rocicorp/zero/react";
import { useMemo } from "react";
import { queries } from "@/zero/queries";
import type { LibraryArtifact, LibraryArtifactStatus } from "../model/artifact";

function runStatus(status: string): LibraryArtifactStatus {
	if (status === "failed") return "error";
	return "running";
}

interface ZeroVideoRunRow {
	id: number;
	title: string;
	status: string;
	artifactId?: number | null;
	workspaceId: number;
	threadId?: number | null;
	createdAt: number;
}

/**
 * In-flight and failed video runs, sourced from Zero by push. A delivered run
 * ("ready") is already represented by its Artifact row, so it is filtered out
 * here to avoid a duplicate card.
 */
export function useLibraryVideoRuns(workspaceId: number): LibraryArtifact[] {
	const [rows] = useZeroQuery(queries.videoRuns.bySpace({ workspaceId }));

	return useMemo(
		() =>
			(rows as ZeroVideoRunRow[])
				.filter((row) => row.status !== "ready")
				.map((row) => ({
					key: `video-run-${row.id}`,
					format: "video",
					artifactId: row.artifactId ?? undefined,
					title: row.title,
					status: runStatus(row.status),
					createdAt: new Date(row.createdAt).toISOString(),
					sourceThreadId: row.threadId ?? null,
				})),
		[rows]
	);
}
