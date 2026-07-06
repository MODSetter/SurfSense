type RouteParams = Record<string, string | string[] | undefined>;

export function getWorkspaceIdParam(params: RouteParams | null | undefined): string | undefined {
	const value = params?.workspace_id ?? params?.search_space_id;
	return Array.isArray(value) ? value[0] : value;
}

export function getWorkspaceIdNumber(params: RouteParams | null | undefined): number | undefined {
	const parsed = Number(getWorkspaceIdParam(params));
	return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
}
