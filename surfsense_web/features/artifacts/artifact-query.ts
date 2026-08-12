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

export const artifactListQueryKey = (workspaceId: number) =>
	["artifact-list", workspaceId] as const;

export async function fetchArtifacts(workspaceId: number) {
	const response = await authenticatedFetch(
		buildBackendUrl(`/api/v1/workspaces/${workspaceId}/artifacts`),
		{ cache: "no-store" }
	);
	if (!response.ok) throw new Error("Artifacts could not be loaded");
	const parsed = ArtifactListSchema.safeParse(await response.json());
	if (!parsed.success) throw new Error("Artifact list response is invalid");
	return parsed.data;
}

export const artifactListQueryOptions = (workspaceId: number) =>
	queryOptions({
		queryKey: artifactListQueryKey(workspaceId),
		queryFn: () => fetchArtifacts(workspaceId),
		staleTime: 30_000,
	});
