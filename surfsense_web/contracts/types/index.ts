import { z } from "zod";

export const paginationQueryParams = z.object({
	limit: z.number().optional(),
	skip: z.number().optional(),
});

export type PaginationQueryParams = z.infer<typeof paginationQueryParams>;
