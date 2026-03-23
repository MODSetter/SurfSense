import { defineQueries } from "@rocicorp/zero";
import { chatSessionQueries, commentQueries, messageQueries } from "./chat";
import { connectorQueries, documentQueries } from "./documents";
import { notificationQueries } from "./inbox";

export const queries = defineQueries({
	notifications: notificationQueries,
	documents: documentQueries,
	connectors: connectorQueries,
	messages: messageQueries,
	comments: commentQueries,
	chatSession: chatSessionQueries,
});
