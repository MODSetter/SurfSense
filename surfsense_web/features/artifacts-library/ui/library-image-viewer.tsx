"use client";

import { Image, ImageLoading } from "@/components/tool-ui/image";
import { useArtifactImage } from "@/features/artifacts/hooks/use-artifact-image";

export function LibraryImageViewer({
	artifactId,
	workspaceId,
	prompt,
}: {
	artifactId: number;
	workspaceId: number;
	prompt: string;
}) {
	const { src, loading, error } = useArtifactImage(workspaceId, artifactId);

	if (loading) return <ImageLoading title="Loading image" maxWidth="640px" />;

	if (error || !src) {
		return (
			<p className="px-6 py-10 text-center text-sm text-muted-foreground">Image not available</p>
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
