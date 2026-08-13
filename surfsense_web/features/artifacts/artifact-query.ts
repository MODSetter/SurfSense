import { queryOptions } from "@tanstack/react-query";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";
import { ArtifactListSchema, ArtifactManifestSchema } from "./model";

export const artifactManifestQueryKey = (workspaceId: number, artifactId: number) =>
	["artifact-manifest", workspaceId, artifactId] as const;

export const artifactManifestQueryOptions = (workspaceId: number, artifactId: number) =>
	queryOptions({
		queryKey: artifactManifestQueryKey(workspaceId, artifactId),
		queryFn: async () => {
			const response = await authenticatedFetch(
				buildBackendUrl(`/api/v1/workspaces/${workspaceId}/artifacts/${artifactId}/manifest`),
				{ cache: "no-store" }
			);
			if (!response.ok) throw new Error("Artifact could not be loaded");
			const parsed = ArtifactManifestSchema.safeParse(await response.json());
			if (!parsed.success) throw new Error("Artifact response is invalid");
			return parsed.data;
		},
		staleTime: 5_000,
		refetchOnWindowFocus: "always",
	});

export const artifactListQueryKey = (workspaceId: number, threadId?: number | null) =>
	threadId == null
		? (["artifact-list", workspaceId] as const)
		: (["artifact-list", workspaceId, threadId] as const);

export async function fetchArtifacts(workspaceId: number, threadId?: number | null) {
	const query = threadId == null ? "" : `?thread_id=${encodeURIComponent(threadId)}`;
	const response = await authenticatedFetch(
		buildBackendUrl(`/api/v1/workspaces/${workspaceId}/artifacts${query}`),
		{ cache: "no-store" }
	);
	if (!response.ok) throw new Error("Artifacts could not be loaded");
	const parsed = ArtifactListSchema.safeParse(await response.json());
	if (!parsed.success) throw new Error("Artifact list response is invalid");
	return parsed.data;
}

export const artifactListQueryOptions = (workspaceId: number, threadId?: number | null) =>
	queryOptions({
		queryKey: artifactListQueryKey(workspaceId, threadId),
		queryFn: () => fetchArtifacts(workspaceId, threadId),
		staleTime: 30_000,
	});
