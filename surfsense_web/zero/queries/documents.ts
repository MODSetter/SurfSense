import { defineQuery } from "@rocicorp/zero";
import { z } from "zod";
import { zql } from "../schema/index";

export const documentQueries = {
	bySpace: defineQuery(z.object({ searchSpaceId: z.number() }), ({ args: { searchSpaceId } }) =>
		zql.documents.where("searchSpaceId", searchSpaceId).orderBy("createdAt", "desc")
	),
};

export const connectorQueries = {
	bySpace: defineQuery(z.object({ searchSpaceId: z.number() }), ({ args: { searchSpaceId } }) =>
		zql.search_source_connectors.where("searchSpaceId", searchSpaceId).orderBy("createdAt", "desc")
	),
};
