import { defineQuery } from "@rocicorp/zero";
import { z } from "zod";
import { zql } from "../schema/index";

export const notificationQueries = {
	byUser: defineQuery(z.object({ userId: z.string() }), ({ args: { userId }, ctx }) => {
		if (!ctx?.userId || userId !== ctx.userId) {
			return zql.notifications.where("userId", "__none__").orderBy("createdAt", "desc");
		}
		return zql.notifications.where("userId", ctx.userId).orderBy("createdAt", "desc");
	}),
};
