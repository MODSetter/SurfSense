import { z } from "zod";

// =============================================================================
// Video presentations — mirror app/schemas/video_presentations.py status enum.
// =============================================================================

export const videoPresentationStatus = z.enum(["pending", "generating", "ready", "failed"]);
export type VideoPresentationStatus = z.infer<typeof videoPresentationStatus>;

export const videoPresentationListItem = z.object({
	id: z.number(),
	title: z.string(),
	status: videoPresentationStatus.default("ready"),
	created_at: z.string(),
	search_space_id: z.number(),
});
export type VideoPresentationListItem = z.infer<typeof videoPresentationListItem>;

export const videoPresentationList = z.array(videoPresentationListItem);
