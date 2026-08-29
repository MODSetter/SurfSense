import { defineQueries } from "@rocicorp/zero";
import { automationRunQueries } from "./automations";
import { chatSessionQueries, commentQueries, messageQueries } from "./chat";
import { connectorQueries, documentQueries } from "./documents";
import { folderQueries } from "./folders";
import { notificationQueries } from "./inbox";
import { podcastRunQueries } from "./podcast-runs";
import { userQueries } from "./user";
import { videoPresentationRunQueries } from "./video-presentation-runs";

export const queries = defineQueries({
	notifications: notificationQueries,
	documents: documentQueries,
	folders: folderQueries,
	connectors: connectorQueries,
	messages: messageQueries,
	comments: commentQueries,
	chatSession: chatSessionQueries,
	user: userQueries,
	automationRuns: automationRunQueries,
	podcastRuns: podcastRunQueries,
	videoRuns: videoPresentationRunQueries,
});
