"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Image, ImageLoading } from "@/components/tool-ui/image";
import { artifactManifestQueryOptions } from "@/features/artifacts/artifact-query";
import { imageGenerationsApiService } from "@/lib/apis/image-generations-api.service";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";

function extractImageSrc(responseData: Record<string, unknown> | null | undefined): string | null {
	const data = (responseData as { data?: unknown } | null | undefined)?.data;
	if (!Array.isArray(data) || data.length === 0) return null;
	const first = data[0] as { url?: string; b64_json?: string };
	if (first?.url) return first.url;
	if (first?.b64_json) return `data:image/png;base64,${first.b64_json}`;
	return null;
}

async function blobUrlFromContentUrl(contentUrl: string): Promise<string> {
	const response = await authenticatedFetch(buildBackendUrl(contentUrl), {
		cache: "no-store",
	});
	if (!response.ok) throw new Error(`Failed to load image: ${response.status}`);
	return URL.createObjectURL(await response.blob());
}

/** Pre-dual-write rows: ImageGeneration detail + tokenized/b64 src. */
function LegacyLibraryImageViewer({ imageId, prompt }: { imageId: number; prompt: string }) {
	const { data, isLoading, error } = useQuery({
		queryKey: ["image-generation-detail", imageId],
		queryFn: () => imageGenerationsApiService.getDetail(imageId),
	});

	if (isLoading) return <ImageLoading title="Loading image" maxWidth="640px" />;

	const src = extractImageSrc(data?.response_data);
	if (error || !src) {
		return (
			<p className="px-6 py-10 text-center text-sm text-muted-foreground">
				{data?.error_message || "Image not available"}
			</p>
		);
	}

	return (
		<Image
			id={`library-image-${imageId}`}
			assetId={String(imageId)}
			src={src}
			alt={prompt}
			title={prompt}
			domain="ai-generated"
			ratio="auto"
			maxWidth="640px"
		/>
	);
}

/** Artifact-backed image under ARTIFACTS_READ. */
function ArtifactLibraryImageViewer({
	artifactId,
	workspaceId,
	prompt,
}: {
	artifactId: number;
	workspaceId: number;
	prompt: string;
}) {
	const manifestQuery = useQuery(artifactManifestQueryOptions(workspaceId, artifactId));
	const primary = manifestQuery.data?.files.find((file) => file.role === "primary");

	const imageQuery = useQuery({
		queryKey: ["artifact-image-blob", workspaceId, artifactId, primary?.file_id],
		enabled: primary != null,
		queryFn: async () => {
			if (!primary) throw new Error("missing primary");
			return blobUrlFromContentUrl(primary.content_url);
		},
		staleTime: 60_000,
	});

	useEffect(() => {
		const url = imageQuery.data;
		return () => {
			if (url) URL.revokeObjectURL(url);
		};
	}, [imageQuery.data]);

	if (manifestQuery.isLoading || imageQuery.isLoading) {
		return <ImageLoading title="Loading image" maxWidth="640px" />;
	}

	const src = imageQuery.data;
	if (manifestQuery.error || imageQuery.error || !src) {
		return (
			<p className="px-6 py-10 text-center text-sm text-muted-foreground">
				Image not available
			</p>
		);
	}

	return (
		<Image
			id={`library-image-${artifactId}`}
			assetId={String(artifactId)}
			src={src}
			alt={prompt}
			title={prompt}
			domain="ai-generated"
			ratio="auto"
			maxWidth="640px"
		/>
	);
}

export function LibraryImageViewer({
	artifactId,
	workspaceId,
	imageId,
	prompt,
}: {
	artifactId?: number;
	workspaceId?: number;
	imageId?: number;
	prompt: string;
}) {
	if (artifactId != null && workspaceId != null) {
		return (
			<ArtifactLibraryImageViewer
				artifactId={artifactId}
				workspaceId={workspaceId}
				prompt={prompt}
			/>
		);
	}
	if (imageId != null) {
		return <LegacyLibraryImageViewer imageId={imageId} prompt={prompt} />;
	}
	return (
		<p className="px-6 py-10 text-center text-sm text-muted-foreground">
			Image not available
		</p>
	);
}
