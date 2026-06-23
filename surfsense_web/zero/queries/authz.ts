import type { Context } from "@/types/zero";

type SpaceScopedQuery = {
	where: (...args: unknown[]) => SpaceScopedQuery;
};

export function canReadSpace(ctx: Context, searchSpaceId: number): boolean {
	return !!ctx?.allowedSpaceIds?.includes(searchSpaceId);
}

export function denySpace<T extends SpaceScopedQuery>(query: T): T {
	return query.where(({ or }: { or: (...args: unknown[]) => unknown }) => or()) as T;
}

export function constrainToAllowedSpaces<T extends SpaceScopedQuery>(query: T, ctx: Context): T {
	const allowedSpaceIds = ctx?.allowedSpaceIds ?? [];
	if (allowedSpaceIds.length === 0) {
		return denySpace(query);
	}
	if (allowedSpaceIds.length === 1) {
		return query.where("searchSpaceId", allowedSpaceIds[0]) as T;
	}
	return query.where(({ cmp, or }: { cmp: (column: string, value: number) => unknown; or: (...args: unknown[]) => unknown }) =>
		or(...allowedSpaceIds.map((id) => cmp("searchSpaceId", id)))
	) as T;
}
