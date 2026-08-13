import { useQuery } from "@tanstack/react-query";
import { fetchArtifacts } from "@/features/artifacts/artifact-query";
import type { ArtifactListItem } from "@/features/artifacts/model";
import { imageGenerationsApiService } from "@/lib/apis/image-generations-api.service";
import { podcastsApiService } from "@/lib/apis/podcasts-api.service";
import { reportsApiService } from "@/lib/apis/reports-api.service";
import { videoPresentationsApiService } from "@/lib/apis/video-presentations-api.service";
import type {
	LibraryArtifact,
	LibraryArtifactKind,
	LibraryArtifactStatus,
} from "../model/artifact";

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

function kindFromFormat(format: string): LibraryArtifactKind | null {
	if (format === "podcast" || format === "video" || format === "image") return format;
	// Office / markdown / pdf / unknown binary formats open in the artifact panel.
	return "file";
}

function fromArtifactRow(row: ArtifactListItem): LibraryArtifact {
	const kind = kindFromFormat(row.format) ?? "file";
	const legacyId =
		row.legacy && row.legacy.kind === kind ? row.legacy.id : undefined;
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

// Artifact list is primary for file + dual-written media. Legacy list endpoints
// only fill gaps for rows not yet dual-written (Phase 4 backfill removes them).
async function fetchLibraryArtifacts(workspaceId: number): Promise<LibraryArtifact[]> {
	const [rows, reports, podcasts, videos, images] = await Promise.all([
		fetchArtifacts(workspaceId).catch(() => []),
		reportsApiService.list(workspaceId).catch(() => []),
		podcastsApiService.list(workspaceId).catch(() => []),
		videoPresentationsApiService.list(workspaceId).catch(() => []),
		imageGenerationsApiService.list(workspaceId).catch(() => []),
	]);

	const artifacts: LibraryArtifact[] = [];
	const covered = {
		podcast: new Set<number>(),
		video: new Set<number>(),
		image: new Set<number>(),
	};

	for (const row of rows) {
		const item = fromArtifactRow(row);
		artifacts.push(item);
		if (
			(item.kind === "podcast" || item.kind === "video" || item.kind === "image") &&
			row.legacy?.kind === item.kind
		) {
			covered[item.kind].add(row.legacy.id);
		}
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

	for (const podcast of podcasts) {
		if (covered.podcast.has(podcast.id)) continue;
		artifacts.push({
			key: `podcast-${podcast.id}`,
			kind: "podcast",
			entityId: podcast.id,
			title: podcast.title,
			status: podcastStatus(podcast.status),
			createdAt: podcast.created_at,
			contentType: "markdown",
			sourceThreadId: podcast.thread_id,
		});
	}

	for (const video of videos) {
		if (covered.video.has(video.id)) continue;
		artifacts.push({
			key: `video-${video.id}`,
			kind: "video",
			entityId: video.id,
			title: video.title,
			status: videoStatus(video.status),
			createdAt: video.created_at,
			contentType: "markdown",
			sourceThreadId: video.thread_id,
		});
	}

	for (const image of images) {
		if (covered.image.has(image.id)) continue;
		artifacts.push({
			key: `image-${image.id}`,
			kind: "image",
			entityId: image.id,
			title: image.prompt,
			status: image.is_success ? "ready" : "error",
			createdAt: image.created_at,
			contentType: "markdown",
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
