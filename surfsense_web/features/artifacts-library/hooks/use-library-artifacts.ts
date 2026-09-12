import { useQuery } from "@tanstack/react-query";
import { artifactListQueryOptions } from "@/features/artifacts/api/artifact-queries";
import { normalizeArtifactFormat } from "@/features/artifacts/lib/artifact-format-catalog";
import type { ArtifactListItem } from "@/features/artifacts/model/artifact";
import type { LibraryArtifact, LibraryArtifactStatus } from "../model/artifact";

function indexingStatus(status: string): LibraryArtifactStatus {
	if (status === "failed") return "error";
	if (status === "ready") return "ready";
	return "running";
}

function fromArtifactRow(row: ArtifactListItem): LibraryArtifact {
	const format = normalizeArtifactFormat(row.format);
	return {
		key: `artifact-${row.artifact_id}`,
		format,
		artifactId: row.artifact_id,
		title: row.title,
		status: indexingStatus(row.indexing_status),
		createdAt: row.created_at,
		sourceThreadId: row.thread_id,
	};
}

// Delivered podcasts arrive as Artifact rows; in-flight/failed runs stream from
// Zero (see useLibraryPodcastRuns), matching how videos are handled.
export function projectLibraryArtifacts(rows: ArtifactListItem[]): LibraryArtifact[] {
	return rows
		.map(fromArtifactRow)
		.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
}

export function useLibraryArtifacts(workspaceId: number) {
	const { data, isLoading, error, refetch } = useQuery({
		...artifactListQueryOptions(workspaceId),
		enabled: Number.isFinite(workspaceId) && workspaceId > 0,
		select: projectLibraryArtifacts,
	});

	return { artifacts: data ?? [], loading: isLoading, error, refresh: refetch };
}
