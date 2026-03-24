import { defineQuery } from "@rocicorp/zero";
import { z } from "zod";
import { zql } from "../schema/index";

export const notificationQueries = {
	byUser: defineQuery(z.object({ userId: z.string() }), ({ args: { userId } }) =>
		zql.notifications.where("userId", userId).orderBy("createdAt", "desc")
	),
};
