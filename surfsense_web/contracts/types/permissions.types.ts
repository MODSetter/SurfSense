import { z } from "zod";

export const permissionInfo = z.object({
	value: z.string(),
	name: z.string(),
	category: z.string(),
	description: z.string(),
});

/**
 * Get permissions
 */
export const getPermissionsResponse = z.object({
	permissions: z.array(permissionInfo),
});

export type PermissionInfo = z.infer<typeof permissionInfo>;
export type GetPermissionsResponse = z.infer<typeof getPermissionsResponse>;
