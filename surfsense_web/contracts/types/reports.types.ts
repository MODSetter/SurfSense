import { z } from "zod";

// =============================================================================
// Reports — mirror app/schemas/reports.py ReportRead (list view, no content).
// Resumes are reports with content_type === "typst".
// =============================================================================

export const reportMetadata = z
	.object({
		status: z.enum(["ready", "failed"]).nullish(),
		word_count: z.number().nullish(),
	})
	.nullish();

export const reportListItem = z.object({
	id: z.number(),
	title: z.string(),
	content_type: z.string().default("markdown"),
	report_metadata: reportMetadata,
	thread_id: z.number().nullish(),
	created_at: z.string(),
});
export type ReportListItem = z.infer<typeof reportListItem>;

export const reportList = z.array(reportListItem);
