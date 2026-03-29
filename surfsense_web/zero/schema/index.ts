import { createBuilder, createSchema, relationships } from "@rocicorp/zero";
import { chatCommentTable, chatSessionStateTable, newChatMessageTable } from "./chat";
import { documentTable, searchSourceConnectorTable } from "./documents";
import { folderTable } from "./folders";
import { notificationTable } from "./inbox";

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
		folderTable,
		searchSourceConnectorTable,
		newChatMessageTable,
		chatCommentTable,
		chatSessionStateTable,
	],
	relationships: [chatCommentRelationships, newChatMessageRelationships],
});

export type Schema = typeof schema;

export const zql = createBuilder(schema);
