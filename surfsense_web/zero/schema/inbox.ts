import { boolean, json, number, string, table } from "@rocicorp/zero";

export const notificationTable = table("notifications")
	.columns({
		id: number(),
		userId: string().from("user_id"),
		searchSpaceId: number().optional().from("search_space_id"),
		type: string(),
		title: string(),
		message: string(),
		read: boolean(),
		metadata: json().optional(),
		createdAt: number().from("created_at"),
		updatedAt: number().optional().from("updated_at"),
	})
	.primaryKey("id");
