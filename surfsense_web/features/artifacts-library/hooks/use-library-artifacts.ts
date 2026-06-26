import { useQuery } from "@tanstack/react-query";
import { imageGenerationsApiService } from "@/lib/apis/image-generations-api.service";
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

// Each list is fetched independently; one failing source shouldn't blank the
// whole library, so failures degrade to an empty slice.
async function fetchLibraryArtifacts(searchSpaceId: number): Promise<LibraryArtifact[]> {
	const [reports, podcasts, videos, images] = await Promise.all([
		reportsApiService.list(searchSpaceId).catch(() => []),
		podcastsApiService.list(searchSpaceId).catch(() => []),
		videoPresentationsApiService.list(searchSpaceId).catch(() => []),
		imageGenerationsApiService.list(searchSpaceId).catch(() => []),
	]);

	const artifacts: LibraryArtifact[] = [];

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

export function useLibraryArtifacts(searchSpaceId: number) {
	const { data, isLoading, error, refetch } = useQuery({
		queryKey: ["artifacts-library", searchSpaceId],
		queryFn: () => fetchLibraryArtifacts(searchSpaceId),
		enabled: Number.isFinite(searchSpaceId) && searchSpaceId > 0,
		staleTime: 60 * 1000,
	});

	return { artifacts: data ?? [], loading: isLoading, error, refresh: refetch };
}
