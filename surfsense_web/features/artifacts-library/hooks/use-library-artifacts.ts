import { useQuery } from "@tanstack/react-query";
import { normalizeArtifactFormat } from "@/features/artifacts/artifact-format-meta";
import { fetchArtifacts } from "@/features/artifacts/artifact-query";
import type { ArtifactListItem } from "@/features/artifacts/model";
import { podcastsApiService } from "@/lib/apis/podcasts-api.service";
import { reportsApiService } from "@/lib/apis/reports-api.service";
import { videoPresentationsApiService } from "@/lib/apis/video-presentations-api.service";
import type { LibraryArtifact, LibraryArtifactStatus } from "../model/artifact";

function podcastStatus(status: string): LibraryArtifactStatus {
	if (status === "ready") return "ready";
	if (status === "failed" || status === "cancelled") return "error";
	return "running";
}

function videoStatus(status: string): LibraryArtifactStatus {
	if (status === "ready") return "ready";
	if (status === "failed") return "error";
	return "running";
}

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

// Legacy list endpoints only cover podcast/video rows with no Artifact row yet.
async function fetchLibraryArtifacts(workspaceId: number): Promise<LibraryArtifact[]> {
	const [rows, reports, podcasts, videos] = await Promise.all([
		fetchArtifacts(workspaceId).catch(() => []),
		reportsApiService.list(workspaceId).catch(() => []),
		podcastsApiService.list(workspaceId).catch(() => []),
		videoPresentationsApiService.list(workspaceId).catch(() => []),
	]);

	const artifacts: LibraryArtifact[] = [];
	const covered = {
		podcast: new Set<number>(),
		video: new Set<number>(),
	};

	for (const row of rows) {
		const item = fromArtifactRow(row);
		artifacts.push(item);
		if (
			(item.format === "podcast" || item.format === "video") &&
			row.legacy?.kind === item.format
		) {
			covered[item.format].add(row.legacy.id);
		}
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

	for (const podcast of podcasts) {
		if (covered.podcast.has(podcast.id)) continue;
		artifacts.push({
			key: `podcast-${podcast.id}`,
			format: "podcast",
			title: podcast.title,
			status: podcastStatus(podcast.status),
			createdAt: podcast.created_at,
			sourceThreadId: podcast.thread_id,
		});
	}

	for (const video of videos) {
		if (covered.video.has(video.id)) continue;
		artifacts.push({
			key: `video-${video.id}`,
			format: "video",
			title: video.title,
			status: videoStatus(video.status),
			createdAt: video.created_at,
			sourceThreadId: video.thread_id,
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
