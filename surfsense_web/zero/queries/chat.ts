import { defineQuery } from "@rocicorp/zero";
import { z } from "zod";
import { zql } from "../schema/index";
import { constrainToAllowedSpaces } from "./authz";

export const messageQueries = {
	byThread: defineQuery(z.object({ threadId: z.number() }), ({ args: { threadId }, ctx }) =>
		zql.new_chat_messages
			.where("threadId", threadId)
			.whereExists("thread", (q) => constrainToAllowedSpaces(q, ctx))
			.orderBy("createdAt", "asc")
	),
};

export const commentQueries = {
	byThread: defineQuery(z.object({ threadId: z.number() }), ({ args: { threadId }, ctx }) =>
		zql.chat_comments
			.where("threadId", threadId)
			.whereExists("thread", (q) => constrainToAllowedSpaces(q, ctx))
			.orderBy("createdAt", "asc")
	),
};

export const chatSessionQueries = {
	byThread: defineQuery(z.object({ threadId: z.number() }), ({ args: { threadId }, ctx }) =>
		zql.chat_session_state
			.where("threadId", threadId)
			.whereExists("thread", (q) => constrainToAllowedSpaces(q, ctx))
			.one()
	),
};

export const threadQueries = {
	byIds: defineQuery(z.object({ ids: z.array(z.number()) }), ({ args: { ids }, ctx }) =>
		constrainToAllowedSpaces(zql.new_chat_threads, ctx)
			.where("id", "IN", ids)
			.where(({ or, cmp }) =>
				or(cmp("createdById", ctx?.userId ?? ""), cmp("visibility", "SEARCH_SPACE"))
			)
	),
};
