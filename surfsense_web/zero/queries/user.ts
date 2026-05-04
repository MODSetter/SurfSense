import { defineQuery } from "@rocicorp/zero";
import { z } from "zod";
import { zql } from "../schema/index";

export const userQueries = {
	me: defineQuery(z.object({}), ({ ctx }) => {
		const userId = ctx?.userId;
		if (!userId) return zql.user.where("id", "__none__").one();
		return zql.user.where("id", userId).one();
	}),
};
