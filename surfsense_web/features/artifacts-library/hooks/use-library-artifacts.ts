import { useQuery } from "@tanstack/react-query";
import { normalizeArtifactFormat } from "@/features/artifacts/artifact-format-meta";
import { fetchArtifacts } from "@/features/artifacts/artifact-query";
import type { ArtifactListItem } from "@/features/artifacts/model";
import { reportsApiService } from "@/lib/apis/reports-api.service";
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
	const [rows, reports] = await Promise.all([
		fetchArtifacts(workspaceId).catch(() => []),
		reportsApiService.list(workspaceId).catch(() => []),
	]);

	const artifacts: LibraryArtifact[] = [];

	for (const row of rows) {
		artifacts.push(fromArtifactRow(row));
	}

	for (const report of reports) {
		const isResume = report.content_type === "typst";
		artifacts.push({
			key: `report-${report.id}`,
			format: isResume ? "resume" : "report",
			title: report.title,
			status: report.report_metadata?.status === "failed" ? "error" : "ready",
			createdAt: report.created_at,
			sourceThreadId: report.thread_id,
		});
	}

	return artifacts.sort(
		(a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
	);
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
