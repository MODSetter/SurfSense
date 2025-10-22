"use server";

import type { PodCastInterface } from "./ChatPanelContainer";

export const generatePodCastAction = async (formData: { prompt: string; chatId: string }) => {
	console.log("Generating podcast");
};

export const getChatPodcastPromise = async (chatId: string): Promise<PodCastInterface> => {
	return Promise.resolve({
		title: "Test",
		podcast_transcript: "Test",
		search_space_id: "Test",
	});
};
