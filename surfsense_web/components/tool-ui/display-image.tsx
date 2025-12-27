"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { AlertCircleIcon, ImageIcon } from "lucide-react";
import { z } from "zod";
import {
	Image,
	ImageErrorBoundary,
	ImageLoading,
	parseSerializableImage,
} from "@/components/tool-ui/image";

// ============================================================================
// Zod Schemas
// ============================================================================

/**
 * Schema for display_image tool arguments
 */
const DisplayImageArgsSchema = z.object({
	src: z.string(),
	alt: z.string().nullish(),
	title: z.string().nullish(),
	description: z.string().nullish(),
});

/**
 * Schema for display_image tool result
 */
const DisplayImageResultSchema = z.object({
	id: z.string(),
	assetId: z.string(),
	src: z.string(),
	alt: z.string().nullish(),
	title: z.string().nullish(),
	description: z.string().nullish(),
	domain: z.string().nullish(),
	ratio: z.string().nullish(),
	error: z.string().nullish(),
});

// ============================================================================
// Types
// ============================================================================

type DisplayImageArgs = z.infer<typeof DisplayImageArgsSchema>;
type DisplayImageResult = z.infer<typeof DisplayImageResultSchema>;

/**
 * Error state component shown when image display fails
 */
function ImageErrorState({ src, error }: { src: string; error: string }) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border border-destructive/20 bg-destructive/5 p-4 max-w-md">
			<div className="flex items-center gap-4">
				<div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-destructive/10">
					<AlertCircleIcon className="size-6 text-destructive" />
				</div>
				<div className="flex-1 min-w-0">
					<p className="font-medium text-destructive text-sm">Failed to display image</p>
					<p className="text-muted-foreground text-xs mt-0.5 truncate">{src}</p>
					<p className="text-muted-foreground text-xs mt-1">{error}</p>
				</div>
			</div>
		</div>
	);
}

/**
 * Cancelled state component
 */
function ImageCancelledState({ src }: { src: string }) {
	return (
		<div className="my-4 rounded-xl border border-muted p-4 text-muted-foreground max-w-md">
			<p className="flex items-center gap-2">
				<ImageIcon className="size-4" />
				<span className="line-through truncate">Image: {src}</span>
			</p>
		</div>
	);
}

/**
 * Parsed Image component with error handling
 * Note: Image component has built-in click handling via href/src,
 * so no additional responseActions needed.
 */
function ParsedImage({ result }: { result: unknown }) {
	const image = parseSerializableImage(result);

	return <Image {...image} maxWidth="420px" />;
}

/**
 * Display Image Tool UI Component
 *
 * This component is registered with assistant-ui to render an image
 * when the display_image tool is called by the agent.
 *
 * It displays images with:
 * - Title and description
 * - Source attribution
 * - Hover overlay effects
 * - Click to open full size
 */
export const DisplayImageToolUI = makeAssistantToolUI<DisplayImageArgs, DisplayImageResult>({
	toolName: "display_image",
	render: function DisplayImageUI({ args, result, status }) {
		const src = args.src || "Unknown";

		// Loading state - tool is still running
		if (status.type === "running" || status.type === "requires-action") {
			return (
				<div className="my-4">
					<ImageLoading title={`Loading image...`} />
				</div>
			);
		}

		// Incomplete/cancelled state
		if (status.type === "incomplete") {
			if (status.reason === "cancelled") {
				return <ImageCancelledState src={src} />;
			}
			if (status.reason === "error") {
				return (
					<ImageErrorState
						src={src}
						error={typeof status.error === "string" ? status.error : "An error occurred"}
					/>
				);
			}
		}

		// No result yet
		if (!result) {
			return (
				<div className="my-4">
					<ImageLoading title="Preparing image..." />
				</div>
			);
		}

		// Error result from the tool
		if (result.error) {
			return <ImageErrorState src={src} error={result.error} />;
		}

		// Success - render the image
		return (
			<div className="my-4">
				<ImageErrorBoundary>
					<ParsedImage result={result} />
				</ImageErrorBoundary>
			</div>
		);
	},
});

export {
	DisplayImageArgsSchema,
	DisplayImageResultSchema,
	type DisplayImageArgs,
	type DisplayImageResult,
};
