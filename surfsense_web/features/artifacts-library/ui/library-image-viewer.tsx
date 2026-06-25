"use client";

import { useQuery } from "@tanstack/react-query";
import { Image, ImageLoading } from "@/components/tool-ui/image";
import { imageGenerationsApiService } from "@/lib/apis/image-generations-api.service";

function extractImageSrc(responseData: Record<string, unknown> | null | undefined): string | null {
	const data = (responseData as { data?: unknown } | null | undefined)?.data;
	if (!Array.isArray(data) || data.length === 0) return null;
	const first = data[0] as { url?: string; b64_json?: string };
	if (first?.url) return first.url;
	if (first?.b64_json) return `data:image/png;base64,${first.b64_json}`;
	return null;
}

export function LibraryImageViewer({ imageId, prompt }: { imageId: number; prompt: string }) {
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
