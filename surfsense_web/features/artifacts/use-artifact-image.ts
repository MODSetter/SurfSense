"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, usePathname } from "next/navigation";
import { useEffect } from "react";
import { artifactManifestQueryOptions } from "@/features/artifacts/artifact-query";
import { baseApiService } from "@/lib/apis/base-api.service";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";

/**
 * Object URL for an artifact's primary file.
 *
 * Artifact content sits behind the session, so `<img src>` cannot fetch it
 * directly; the blob is fetched and wrapped, then revoked on unmount. Public
 * shares have no session and go through the share token instead.
 */
export function useArtifactImage(workspaceId: number, artifactId: number) {
	const params = useParams();
	const pathname = usePathname();
	const shareToken =
		pathname?.startsWith("/public/") && typeof params?.token === "string" ? params.token : null;

	const manifestQuery = useQuery({
		...artifactManifestQueryOptions(workspaceId, artifactId),
		enabled: shareToken == null,
	});
	const primary = manifestQuery.data?.files.find((file) => file.role === "primary");

	const imageQuery = useQuery({
		queryKey: ["artifact-image-blob", shareToken, workspaceId, artifactId, primary?.file_id],
		enabled: shareToken != null || primary != null,
		queryFn: async () => {
			const blob = shareToken
				? await baseApiService.getBlob(
						`/api/v1/public/${shareToken}/artifacts/${artifactId}/content`
					)
				: await fetchPrimary(primary?.content_url);
			return URL.createObjectURL(blob);
		},
		staleTime: 60_000,
	});

	useEffect(() => {
		const url = imageQuery.data;
		return () => {
			if (url) URL.revokeObjectURL(url);
		};
	}, [imageQuery.data]);

	return {
		src: imageQuery.data,
		loading: manifestQuery.isLoading || imageQuery.isLoading,
		error: manifestQuery.error ?? imageQuery.error,
	};
}

async function fetchPrimary(contentUrl: string | undefined): Promise<Blob> {
	if (!contentUrl) throw new Error("missing primary file");
	const response = await authenticatedFetch(buildBackendUrl(contentUrl), {
		cache: "no-store",
	});
	if (!response.ok) throw new Error(`Failed to load image: ${response.status}`);
	return response.blob();
}
