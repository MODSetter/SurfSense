import { defineQueries } from "@rocicorp/zero";
import { automationRunQueries } from "./automations";
import { chatSessionQueries, commentQueries, messageQueries, threadQueries } from "./chat";
import { connectorQueries, documentQueries } from "./documents";
import { folderQueries } from "./folders";
import { notificationQueries } from "./inbox";
import { podcastQueries } from "./podcasts";
import { userQueries } from "./user";

export const queries = defineQueries({
	notifications: notificationQueries,
	documents: documentQueries,
	folders: folderQueries,
	connectors: connectorQueries,
	messages: messageQueries,
	comments: commentQueries,
	chatSession: chatSessionQueries,
	threads: threadQueries,
	user: userQueries,
	automationRuns: automationRunQueries,
	podcasts: podcastQueries,
});
