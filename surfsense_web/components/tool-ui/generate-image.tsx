"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { AlertCircleIcon, ImageIcon } from "lucide-react";
import { z } from "zod";
import { Image, ImageErrorBoundary, ImageLoading } from "@/components/tool-ui/image";
import { useArtifactImage } from "@/features/artifacts/hooks/use-artifact-image";

const GenerateImageArgsSchema = z.object({
	prompt: z.string(),
	n: z.number().nullish(),
});

const GenerateImageResultSchema = z.object({
	id: z.string(),
	artifact_id: z.number(),
	workspace_id: z.number(),
	alt: z.string().nullish(),
	title: z.string().nullish(),
	description: z.string().nullish(),
	domain: z.string().nullish(),
	ratio: z.enum(["auto", "1:1", "4:3", "16:9", "9:16", "21:9"]).nullish(),
	generated: z.boolean().nullish(),
	prompt: z.string().nullish(),
	error: z.string().nullish(),
});

type GenerateImageArgs = z.infer<typeof GenerateImageArgsSchema>;
type GenerateImageResult = z.infer<typeof GenerateImageResultSchema>;

function ImageErrorState({ prompt, error }: { prompt: string; error: string }) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border border-destructive/20 bg-destructive/5 p-4 max-w-md">
			<div className="flex items-center gap-4">
				<div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-destructive/10">
					<AlertCircleIcon className="size-6 text-destructive" />
				</div>
				<div className="flex-1 min-w-0">
					<p className="font-medium text-destructive text-sm">Image generation failed</p>
					<p className="text-muted-foreground text-xs mt-0.5 truncate">{prompt}</p>
					<p className="text-muted-foreground text-xs mt-1">{error}</p>
				</div>
			</div>
		</div>
	);
}

function ImageCancelledState({ prompt }: { prompt: string }) {
	return (
		<div className="my-4 rounded-xl border border-muted p-4 text-muted-foreground max-w-md">
			<p className="flex items-center gap-2">
				<ImageIcon className="size-4" />
				<span className="line-through truncate">Generate: {prompt}</span>
			</p>
		</div>
	);
}

function ArtifactImage({ result }: { result: GenerateImageResult }) {
	const { src, loading, error } = useArtifactImage(result.workspace_id, result.artifact_id);

	if (loading) return <ImageLoading title="Loading image" maxWidth="512px" />;
	if (error || !src) {
		return <ImageErrorState prompt={result.prompt ?? ""} error="Image not available" />;
	}

	return (
		<Image
			id={result.id}
			assetId={String(result.artifact_id)}
			src={src}
			alt={result.alt ?? result.prompt ?? "Generated image"}
			title={result.title ?? undefined}
			description={result.description ?? undefined}
			domain={result.domain ?? undefined}
			ratio={result.ratio ?? undefined}
			maxWidth="512px"
		/>
	);
}

/**
 * Tool UI for generate_image — renders the generated image directly
 * from the tool result directly.
 */
export const GenerateImageToolUI = ({
	args,
	result,
	status,
}: ToolCallMessagePartProps<GenerateImageArgs, GenerateImageResult>) => {
	const prompt = args.prompt || "Generating image...";

	if (status.type === "running" || status.type === "requires-action") {
		return (
			<div className="my-4">
				<ImageLoading title="Generating image" />
			</div>
		);
	}

	if (status.type === "incomplete") {
		if (status.reason === "cancelled") {
			return <ImageCancelledState prompt={prompt} />;
		}
		if (status.reason === "error") {
			return (
				<ImageErrorState
					prompt={prompt}
					error={typeof status.error === "string" ? status.error : "An error occurred"}
				/>
			);
		}
	}

	if (!result) {
		return (
			<div className="my-4">
				<ImageLoading title="Loading" />
			</div>
		);
	}

	if (result.error || result.artifact_id == null) {
		return <ImageErrorState prompt={prompt} error={result.error ?? "Image not available"} />;
	}

	return (
		<div className="my-4">
			<ImageErrorBoundary>
				<ArtifactImage result={result} />
			</ImageErrorBoundary>
		</div>
	);
};

export {
	type GenerateImageArgs,
	GenerateImageArgsSchema,
	type GenerateImageResult,
	GenerateImageResultSchema,
};
