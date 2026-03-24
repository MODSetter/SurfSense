"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { AlertCircleIcon, ImageIcon } from "lucide-react";
import { z } from "zod";
import {
	Image,
	ImageErrorBoundary,
	ImageLoading,
	parseSerializableImage,
} from "@/components/tool-ui/image";

const GenerateImageArgsSchema = z.object({
	prompt: z.string(),
	n: z.number().nullish(),
});

const GenerateImageResultSchema = z.object({
	id: z.string(),
	assetId: z.string(),
	src: z.string(),
	alt: z.string().nullish(),
	title: z.string().nullish(),
	description: z.string().nullish(),
	domain: z.string().nullish(),
	ratio: z.string().nullish(),
	generated: z.boolean().nullish(),
	prompt: z.string().nullish(),
	image_count: z.number().nullish(),
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

function ParsedImage({ result }: { result: unknown }) {
	const image = parseSerializableImage(result);
	return (
		<Image
			id={image.id}
			assetId={image.assetId}
			src={image.src}
			alt={image.alt}
			title={image.title ?? undefined}
			description={image.description ?? undefined}
			href={image.href ?? undefined}
			domain={image.domain ?? undefined}
			ratio={image.ratio ?? undefined}
			source={image.source ?? undefined}
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

	if (result.error) {
		return <ImageErrorState prompt={prompt} error={result.error} />;
	}

	return (
		<div className="my-4">
			<ImageErrorBoundary>
				<ParsedImage result={result} />
			</ImageErrorBoundary>
		</div>
	);
};

export {
	GenerateImageArgsSchema,
	GenerateImageResultSchema,
	type GenerateImageArgs,
	type GenerateImageResult,
};
