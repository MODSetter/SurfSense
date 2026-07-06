import { z } from "zod";
import {
	languageOptions,
	type PodcastSpec,
	podcastDetail,
	podcastSummaryList,
	updateSpecRequest,
	voiceOption,
} from "@/contracts/types/podcast.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

const BASE = "/api/v1/podcasts";

const voiceOptionList = z.array(voiceOption);

class PodcastsApiService {
	list = async (searchSpaceId: number, limit = 200) => {
		const qs = new URLSearchParams({
			workspace_id: String(searchSpaceId),
			limit: String(limit),
		}).toString();
		return baseApiService.get(`${BASE}?${qs}`, podcastSummaryList);
	};

	// Full state including the deserialized brief and transcript; thin lifecycle
	// fields (status, spec, spec_version) also arrive live via Zero.
	getDetail = async (podcastId: number) => {
		return baseApiService.get(`${BASE}/${podcastId}`, podcastDetail);
	};

	// Guarded by the version the caller last saw; the backend answers 409 when
	// the brief changed underneath them.
	updateSpec = async (podcastId: number, spec: PodcastSpec, expectedVersion: number) => {
		const parsed = updateSpecRequest.safeParse({ spec, expected_version: expectedVersion });
		if (!parsed.success) {
			throw new ValidationError(
				`Invalid request: ${parsed.error.issues.map((i) => i.message).join(", ")}`
			);
		}
		return baseApiService.patch(`${BASE}/${podcastId}/spec`, podcastDetail, {
			body: parsed.data,
		});
	};

	approveBrief = async (podcastId: number) => {
		return baseApiService.post(`${BASE}/${podcastId}/brief/approve`, podcastDetail);
	};

	// Reopens the brief gate; the transcript and audio are replaced once the
	// user re-approves.
	regenerate = async (podcastId: number) => {
		return baseApiService.post(`${BASE}/${podcastId}/transcript/regenerate`, podcastDetail);
	};

	// Backs out of a regeneration: the podcast returns to ready with its
	// existing audio untouched. 409 when there is no episode to fall back to.
	revertRegeneration = async (podcastId: number) => {
		return baseApiService.post(`${BASE}/${podcastId}/regenerate/revert`, podcastDetail);
	};

	// Only for podcasts that have produced nothing yet; once an episode
	// exists the backend refuses (409) and revertRegeneration is the way back.
	cancel = async (podcastId: number) => {
		return baseApiService.post(`${BASE}/${podcastId}/cancel`, podcastDetail);
	};

	listVoices = async (language?: string) => {
		const qs = language ? `?${new URLSearchParams({ language })}` : "";
		return baseApiService.get(`${BASE}/voices${qs}`, voiceOptionList);
	};

	// The languages the active provider can offer; the brief form renders
	// exactly this list and only opens free entry when the backend allows it.
	listLanguages = async () => {
		return baseApiService.get(`${BASE}/languages`, languageOptions);
	};

	// A short audio sample of a voice, cached server-side per voice.
	previewVoice = async (voiceId: string) => {
		return baseApiService.getBlob(`${BASE}/voices/${encodeURIComponent(voiceId)}/preview`);
	};
}

export const podcastsApiService = new PodcastsApiService();
