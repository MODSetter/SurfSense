import { defineQuery } from "@rocicorp/zero";
import { z } from "zod";
import { zql } from "../schema/index";

export const messageQueries = {
	byThread: defineQuery(z.object({ threadId: z.number() }), ({ args: { threadId } }) =>
		zql.new_chat_messages.where("threadId", threadId).orderBy("createdAt", "asc")
	),
};

export const commentQueries = {
	byThread: defineQuery(z.object({ threadId: z.number() }), ({ args: { threadId } }) =>
		zql.chat_comments.where("threadId", threadId).orderBy("createdAt", "asc")
	),
};

export const chatSessionQueries = {
	byThread: defineQuery(z.object({ threadId: z.number() }), ({ args: { threadId } }) =>
		zql.chat_session_state.where("threadId", threadId).one()
	),
};
