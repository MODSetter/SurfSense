import { useQuery } from "@tanstack/react-query";
import { fetchArtifacts } from "@/features/artifacts/artifact-query";
import type { ArtifactListItem } from "@/features/artifacts/model";
import { reportsApiService } from "@/lib/apis/reports-api.service";
import type {
	LibraryArtifact,
	LibraryArtifactKind,
	LibraryArtifactStatus,
} from "../model/artifact";

function indexingStatus(status: string): LibraryArtifactStatus {
	if (status === "failed") return "error";
	if (status === "ready") return "ready";
	return "running";
}

function kindFromFormat(format: string): LibraryArtifactKind | null {
	if (format === "podcast" || format === "video" || format === "image") return format;
	// Office / markdown / pdf / unknown binary formats open in the artifact panel.
	return "file";
}

function fromArtifactRow(row: ArtifactListItem): LibraryArtifact {
	const kind = kindFromFormat(row.format) ?? "file";
	const legacyId = row.legacy && row.legacy.kind === kind ? row.legacy.id : undefined;
	return {
		key: `${kind}-${row.artifact_id}`,
		kind,
		entityId: kind === "file" ? row.artifact_id : (legacyId ?? row.artifact_id),
		artifactId: row.artifact_id,
		legacyEntityId: legacyId,
		title: row.title,
		status: indexingStatus(row.indexing_status),
		createdAt: row.created_at,
		contentType: kind === "file" ? "file" : "markdown",
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
			kind: isResume ? "resume" : "report",
			entityId: report.id,
			title: report.title,
			status: report.report_metadata?.status === "failed" ? "error" : "ready",
			createdAt: report.created_at,
			contentType: isResume ? "typst" : "markdown",
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
