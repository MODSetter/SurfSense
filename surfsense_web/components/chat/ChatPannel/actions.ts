"use server";

import type { PodCastInterface, PodcastGenerationState } from "./ChatPanelContainer";

export const generatePodCastAction = async (
	formData: PodcastGenerationState
): Promise<PodCastInterface> => {
	return Promise.resolve({
		title: "Test",
		podcast_transcript: "Test",
		search_space_id: "Test",
	});
};

export const getChatPodcastPromise = async (chatId: string): Promise<PodCastInterface> => {
	return Promise.resolve({
		title: "Test",
		podcast_transcript: "Test",
		search_space_id: "Test",
	});
};
