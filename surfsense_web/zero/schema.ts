import { createSchema, createBuilder, relationships } from "@rocicorp/zero";
import { chatCommentTable, chatSessionStateTable, newChatMessageTable } from "./tables/chat";
import { documentTable, searchSourceConnectorTable } from "./tables/documents";
import { notificationTable } from "./tables/inbox";

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
}));

const newChatMessageRelationships = relationships(newChatMessageTable, ({ many }) => ({
	comments: many({
		sourceField: ["id"],
		destSchema: chatCommentTable,
		destField: ["messageId"],
	}),
}));

export const schema = createSchema({
	tables: [
		notificationTable,
		documentTable,
		searchSourceConnectorTable,
		newChatMessageTable,
		chatCommentTable,
		chatSessionStateTable,
	],
	relationships: [chatCommentRelationships, newChatMessageRelationships],
});

export type Schema = typeof schema;

export const zql = createBuilder(schema);
