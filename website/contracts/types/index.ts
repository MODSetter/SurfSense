import { z } from "zod";

export const paginationQueryParams = z.object({
	limit: z.number().optional(),
	skip: z.number().optional(),
	// OR
	page: z.number().optional(),
	page_size: z.number().optional(),
	// TODO: Normalize to page/page_size or limit/skip in backend
});

export type PaginationQueryParams = z.infer<typeof paginationQueryParams>;
