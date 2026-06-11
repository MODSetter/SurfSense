"use client";

import { useQuery } from "@rocicorp/zero/react";
import { useMemo } from "react";
import { type PodcastSpec, type PodcastStatus, podcastSpec } from "@/contracts/types/podcast.types";
import { queries } from "@/zero/queries";

/**
 * Thin live row sourced from Zero's `podcasts` publication. Drives the
 * lifecycle UI by push (no polling); heavy fields (transcript, audio) stay on
 * REST and are fetched lazily when a gate or the player needs them.
 */
export interface LivePodcast {
	id: number;
	title: string;
	status: PodcastStatus;
	spec: PodcastSpec | null;
	specVersion: number;
	durationSeconds: number | null;
	error: string | null;
	searchSpaceId: number;
	threadId: number | null;
}

interface UsePodcastLiveResult {
	podcast: LivePodcast | undefined;
	isLoading: boolean;
}

export function usePodcastLive(podcastId: number | undefined): UsePodcastLiveResult {
	const [row, result] = useQuery(queries.podcasts.byId({ podcastId: podcastId ?? -1 }));

	const podcast = useMemo<LivePodcast | undefined>(() => {
		if (!podcastId || !row) return undefined;
		return {
			id: row.id,
			title: row.title,
			status: row.status as PodcastStatus,
			spec: parseSpec(row.spec),
			specVersion: row.specVersion,
			durationSeconds: row.durationSeconds ?? null,
			error: row.error ?? null,
			searchSpaceId: row.searchSpaceId,
			threadId: row.threadId ?? null,
		};
	}, [podcastId, row]);

	// Pre-hydration window: no row AND Zero hasn't confirmed completeness yet.
	const isLoading = !!podcastId && !row && result.type !== "complete";

	return { podcast, isLoading };
}

/** The JSONB column holds the snake_case spec; reject anything malformed. */
function parseSpec(raw: unknown): PodcastSpec | null {
	if (raw == null) return null;
	const parsed = podcastSpec.safeParse(raw);
	return parsed.success ? parsed.data : null;
}
