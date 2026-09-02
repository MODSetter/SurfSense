import { type QueryClient, queryOptions } from "@tanstack/react-query";
import { ArtifactListSchema, ArtifactManifestSchema } from "@/features/artifacts/model/artifact";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";

export const artifactManifestQueryKey = (workspaceId: number, artifactId: number) =>
	["artifact-manifest", workspaceId, artifactId] as const;

const artifactImageBlobQueryPrefix = (workspaceId: number, artifactId: number) =>
	["artifact-image-blob", workspaceId, artifactId] as const;

export const artifactImageBlobQueryKey = (
	workspaceId: number,
	artifactId: number,
	shareToken: string | null,
	fileId?: number
) => [...artifactImageBlobQueryPrefix(workspaceId, artifactId), shareToken, fileId] as const;

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
		refetchOnWindowFocus: "always",
	});

/** Refresh every cache surface that can retain an artifact revision. */
export async function invalidatePublishedArtifact(
	queryClient: QueryClient,
	workspaceId: number,
	artifactId: number
): Promise<void> {
	const blobPrefixes = [artifactImageBlobQueryPrefix(workspaceId, artifactId)];
	await Promise.all(blobPrefixes.map((queryKey) => queryClient.cancelQueries({ queryKey })));
	for (const queryKey of blobPrefixes) {
		queryClient.setQueriesData<string | null>({ queryKey }, null);
		queryClient.removeQueries({ queryKey });
	}

	await Promise.all([
		queryClient.resetQueries({
			queryKey: artifactManifestQueryKey(workspaceId, artifactId),
			exact: true,
		}),
		queryClient.invalidateQueries({ queryKey: artifactListQueryKey(workspaceId) }),
	]);
}
