import { createBuilder, createSchema, relationships } from "@rocicorp/zero";
import { automationRunTable, automationTable } from "./automations";
import {
	chatCommentTable,
	chatSessionStateTable,
	newChatMessageTable,
	newChatThreadTable,
} from "./chat";
import { documentTable, searchSourceConnectorTable } from "./documents";
import { folderTable } from "./folders";
import { notificationTable } from "./inbox";
import { podcastTable } from "./podcasts";
import { userTable } from "./user";

const chatCommentRelationships = relationships(chatCommentTable, ({ one }) => ({
	message: one({
		sourceField: ["messageId"],
		destSchema: newChatMessageTable,
		destField: ["id"],
	}),
	parent: one({
		sourceField: ["parentId"],
		destSchema: chatCommentTable,
		destField: ["id"],
	}),
	thread: one({
		sourceField: ["threadId"],
		destSchema: newChatThreadTable,
		destField: ["id"],
	}),
}));

const newChatMessageRelationships = relationships(newChatMessageTable, ({ one, many }) => ({
	comments: many({
		sourceField: ["id"],
		destSchema: chatCommentTable,
		destField: ["messageId"],
	}),
	thread: one({
		sourceField: ["threadId"],
		destSchema: newChatThreadTable,
		destField: ["id"],
	}),
}));

const chatSessionStateThreadRelationships = relationships(chatSessionStateTable, ({ one }) => ({
	thread: one({
		sourceField: ["threadId"],
		destSchema: newChatThreadTable,
		destField: ["id"],
	}),
}));

const automationRunRelationships = relationships(automationRunTable, ({ one }) => ({
	automation: one({
		sourceField: ["automationId"],
		destSchema: automationTable,
		destField: ["id"],
	}),
}));

export const schema = createSchema({
	tables: [
		notificationTable,
		documentTable,
		folderTable,
		searchSourceConnectorTable,
		newChatThreadTable,
		newChatMessageTable,
		chatCommentTable,
		chatSessionStateTable,
		userTable,
		automationTable,
		automationRunTable,
		podcastTable,
	],
	relationships: [
		chatCommentRelationships,
		newChatMessageRelationships,
		chatSessionStateThreadRelationships,
		automationRunRelationships,
	],
});

export type Schema = typeof schema;

export const zql = createBuilder(schema);
