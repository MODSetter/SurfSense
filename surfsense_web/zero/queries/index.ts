import { defineQueries } from "@rocicorp/zero";
import { chatSessionQueries, commentQueries, messageQueries } from "./chat";
import { connectorQueries, documentQueries } from "./documents";
import { folderQueries } from "./folders";
import { notificationQueries } from "./inbox";

export const queries = defineQueries({
	notifications: notificationQueries,
	documents: documentQueries,
	folders: folderQueries,
	connectors: connectorQueries,
	messages: messageQueries,
	comments: commentQueries,
	chatSession: chatSessionQueries,
});
