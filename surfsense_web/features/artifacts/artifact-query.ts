import { queryOptions } from "@tanstack/react-query";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";
import { ArtifactContentSchema } from "./model";

export const artifactQueryKey = (workspaceId: number, documentId: number) =>
	["artifact", workspaceId, documentId] as const;

export const artifactQueryOptions = (workspaceId: number, documentId: number) =>
	queryOptions({
		queryKey: artifactQueryKey(workspaceId, documentId),
		queryFn: async () => {
			const response = await authenticatedFetch(
				buildBackendUrl(`/api/v1/workspaces/${workspaceId}/documents/${documentId}/editor-content`),
				{ cache: "no-store" }
			);
			if (!response.ok) throw new Error("Artifact could not be loaded");
			const parsed = ArtifactContentSchema.safeParse(await response.json());
			if (!parsed.success) throw new Error("Artifact response is invalid");
			return parsed.data;
		},
		staleTime: 5_000,
		refetchOnWindowFocus: "always",
	});
