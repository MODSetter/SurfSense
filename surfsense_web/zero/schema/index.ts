import { createBuilder, createSchema, relationships } from "@rocicorp/zero";
import { automationRunTable, automationTable } from "./automations";
import {
	chatCommentTable,
	chatSessionStateTable,
	newChatMessageTable,
	newChatThreadTable,
} from "./chat";
import { deliverableJobTable } from "./deliverable-jobs";
import { documentTable, searchSourceConnectorTable } from "./documents";
import { folderTable } from "./folders";
import { notificationTable } from "./inbox";
import { podcastRunTable } from "./podcast-runs";
import { userTable } from "./user";
import { videoPresentationRunTable } from "./video-presentation-runs";

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
		podcastRunTable,
		videoPresentationRunTable,
		deliverableJobTable,
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
