import { defineQuery } from "@rocicorp/zero";
import { z } from "zod";
import { zql } from "../schema/index";

export const folderQueries = {
	bySpace: defineQuery(z.object({ searchSpaceId: z.number() }), ({ args: { searchSpaceId } }) =>
		zql.folders.where("searchSpaceId", searchSpaceId).orderBy("position", "asc")
	),
};
