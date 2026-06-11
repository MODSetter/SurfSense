import { z } from "zod";
import {
	type PodcastSpec,
	podcastDetail,
	updateSpecRequest,
	voiceOption,
} from "@/contracts/types/podcast.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

const BASE = "/api/v1/podcasts";

const voiceOptionList = z.array(voiceOption);

class PodcastsApiService {
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

	cancel = async (podcastId: number) => {
		return baseApiService.post(`${BASE}/${podcastId}/cancel`, podcastDetail);
	};

	listVoices = async (language?: string) => {
		const qs = language ? `?${new URLSearchParams({ language })}` : "";
		return baseApiService.get(`${BASE}/voices${qs}`, voiceOptionList);
	};

	// A short audio sample of a voice, cached server-side per voice.
	previewVoice = async (voiceId: string) => {
		return baseApiService.getBlob(`${BASE}/voices/${encodeURIComponent(voiceId)}/preview`);
	};
}

export const podcastsApiService = new PodcastsApiService();
