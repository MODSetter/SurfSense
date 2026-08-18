import { useQuery } from "@tanstack/react-query";
import { normalizeArtifactFormat } from "@/features/artifacts/artifact-format-meta";
import { fetchArtifacts } from "@/features/artifacts/artifact-query";
import type { ArtifactListItem } from "@/features/artifacts/model";
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
async function fetchLibraryArtifacts(workspaceId: number): Promise<LibraryArtifact[]> {
	const rows = await fetchArtifacts(workspaceId).catch(() => []);
	return rows
		.map(fromArtifactRow)
		.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
}

export function useLibraryArtifacts(workspaceId: number) {
	const { data, isLoading, error, refetch } = useQuery({
		queryKey: ["artifacts-library", workspaceId],
		queryFn: () => fetchLibraryArtifacts(workspaceId),
		enabled: Number.isFinite(workspaceId) && workspaceId > 0,
		staleTime: 60 * 1000,
	});

	return { artifacts: data ?? [], loading: isLoading, error, refresh: refetch };
}
