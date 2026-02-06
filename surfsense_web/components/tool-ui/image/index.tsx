"use client";

import { ExternalLinkIcon, ImageIcon, SparklesIcon } from "lucide-react";
import NextImage from "next/image";
import { Component, type ReactNode, useState } from "react";
import { z } from "zod";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

/**
 * Zod schemas for runtime validation
 */
const AspectRatioSchema = z.enum(["1:1", "4:3", "16:9", "9:16", "21:9", "auto"]);
const ImageFitSchema = z.enum(["cover", "contain"]);

const ImageSourceSchema = z.object({
	label: z.string(),
	iconUrl: z.string().nullish(),
	url: z.string().nullish(),
});

const SerializableImageSchema = z.object({
	id: z.string(),
	assetId: z.string(),
	src: z.string(),
	alt: z.string().nullish(),
	title: z.string().nullish(),
	description: z.string().nullish(),
	href: z.string().nullish(),
	domain: z.string().nullish(),
	ratio: AspectRatioSchema.nullish(),
	source: ImageSourceSchema.nullish(),
});

/**
 * Types derived from Zod schemas
 */
type AspectRatio = z.infer<typeof AspectRatioSchema>;
type ImageFit = z.infer<typeof ImageFitSchema>;
type ImageSource = z.infer<typeof ImageSourceSchema>;
export type SerializableImage = z.infer<typeof SerializableImageSchema>;

/**
 * Props for the Image component
 */
export interface ImageProps {
	id: string;
	assetId: string;
	src: string;
	alt?: string;
	title?: string;
	description?: string;
	href?: string;
	domain?: string;
	ratio?: AspectRatio;
	fit?: ImageFit;
	source?: ImageSource;
	maxWidth?: string;
	className?: string;
}

/**
 * Parse and validate serializable image from tool result
 * Returns a valid SerializableImage with fallback values for missing optional fields
 */
export function parseSerializableImage(result: unknown): SerializableImage & { alt: string } {
	const parsed = SerializableImageSchema.safeParse(result);

	if (!parsed.success) {
		console.warn("Invalid image data:", parsed.error.issues);

		const obj = (result && typeof result === "object" ? result : {}) as Record<string, unknown>;

		if (
			typeof obj.id === "string" &&
			typeof obj.assetId === "string" &&
			typeof obj.src === "string"
		) {
			return {
				id: obj.id,
				assetId: obj.assetId,
				src: obj.src,
				alt: typeof obj.alt === "string" ? obj.alt : "Image",
				title: typeof obj.title === "string" ? obj.title : undefined,
				description: typeof obj.description === "string" ? obj.description : undefined,
				href: typeof obj.href === "string" ? obj.href : undefined,
				domain: typeof obj.domain === "string" ? obj.domain : undefined,
				ratio: undefined,
				source: undefined,
			};
		}

		throw new Error(`Invalid image: ${parsed.error.issues.map((i) => i.message).join(", ")}`);
	}

	return {
		...parsed.data,
		alt: parsed.data.alt ?? "Image",
	};
}

/**
 * Get aspect ratio class based on ratio prop (used for fixed-ratio images only)
 */
function getAspectRatioClass(ratio?: AspectRatio): string {
	switch (ratio) {
		case "1:1":
			return "aspect-square";
		case "4:3":
			return "aspect-[4/3]";
		case "16:9":
			return "aspect-video";
		case "9:16":
			return "aspect-[9/16]";
		case "21:9":
			return "aspect-[21/9]";
		default:
			return "aspect-[4/3]";
	}
}

/**
 * Error boundary for Image component
 */
interface ImageErrorBoundaryState {
	hasError: boolean;
	error?: Error;
}

export class ImageErrorBoundary extends Component<
	{ children: ReactNode },
	ImageErrorBoundaryState
> {
	constructor(props: { children: ReactNode }) {
		super(props);
		this.state = { hasError: false };
	}

	static getDerivedStateFromError(error: Error): ImageErrorBoundaryState {
		return { hasError: true, error };
	}

	render() {
		if (this.state.hasError) {
			return (
				<Card className="w-full max-w-md overflow-hidden">
					<div className="aspect-square bg-muted flex items-center justify-center">
						<div className="flex flex-col items-center gap-2 text-muted-foreground">
							<ImageIcon className="size-8" />
							<p className="text-sm">Failed to load image</p>
						</div>
					</div>
				</Card>
			);
		}

		return this.props.children;
	}
}

/**
 * Loading skeleton for Image
 */
export function ImageSkeleton({ maxWidth = "512px" }: { maxWidth?: string }) {
	return (
		<Card className="w-full overflow-hidden animate-pulse" style={{ maxWidth }}>
			<div className="aspect-square bg-muted flex items-center justify-center">
				<ImageIcon className="size-12 text-muted-foreground/30" />
			</div>
		</Card>
	);
}

/**
 * Image Loading State
 */
export function ImageLoading({ title = "Loading image..." }: { title?: string }) {
	return (
		<Card className="w-full max-w-md overflow-hidden">
			<div className="aspect-square bg-muted flex items-center justify-center">
				<div className="flex flex-col items-center gap-3">
					<Spinner size="lg" className="text-muted-foreground" />
					<p className="text-muted-foreground text-sm">{title}</p>
				</div>
			</div>
		</Card>
	);
}

/**
 * Image Component
 *
 * Display images with metadata and attribution.
 * - For "auto" ratio: renders the image at natural dimensions (no cropping)
 * - For fixed ratios: uses a fixed aspect container with object-cover
 * - Features hover overlay with title, description, and source attribution.
 */
export function Image({
	id,
	src,
	alt = "Image",
	title,
	description,
	href,
	domain,
	ratio = "auto",
	fit = "cover",
	source,
	maxWidth = "512px",
	className,
}: ImageProps) {
	const [isHovered, setIsHovered] = useState(false);
	const [imageError, setImageError] = useState(false);
	const [imageLoaded, setImageLoaded] = useState(false);
	const displayDomain = domain || source?.label;
	const isGenerated = domain === "ai-generated";
	const isAutoRatio = !ratio || ratio === "auto";

	const handleClick = () => {
		const targetUrl = href || source?.url || src;
		if (targetUrl) {
			window.open(targetUrl, "_blank", "noopener,noreferrer");
		}
	};

	if (imageError) {
		return (
			<Card id={id} className={cn("w-full overflow-hidden", className)} style={{ maxWidth }}>
				<div className="aspect-square bg-muted flex items-center justify-center">
					<div className="flex flex-col items-center gap-2 text-muted-foreground">
						<ImageIcon className="size-8" />
						<p className="text-sm">Image not available</p>
					</div>
				</div>
			</Card>
		);
	}

	return (
		<Card
			id={id}
			className={cn(
				"group w-full overflow-hidden cursor-pointer transition-shadow duration-200 hover:shadow-lg",
				isGenerated && "ring-1 ring-primary/10",
				className
			)}
			style={{ maxWidth }}
			onClick={handleClick}
			onMouseEnter={() => setIsHovered(true)}
			onMouseLeave={() => setIsHovered(false)}
			onKeyDown={(e) => {
				if (e.key === "Enter" || e.key === " ") {
					e.preventDefault();
					handleClick();
				}
			}}
			role="button"
			tabIndex={0}
		>
			<div className="relative w-full overflow-hidden bg-muted">
				{isAutoRatio ? (
					/* Auto ratio: image renders at natural dimensions, no cropping */
					<>
						{!imageLoaded && (
							<div className="aspect-square flex items-center justify-center">
								<Spinner size="lg" className="text-muted-foreground" />
							</div>
						)}
						{/* eslint-disable-next-line @next/next/no-img-element */}
						<img
							src={src}
							alt={alt}
							className={cn(
								"w-full h-auto transition-transform duration-300",
								isHovered && "scale-[1.02]",
								!imageLoaded && "hidden"
							)}
							onLoad={() => setImageLoaded(true)}
							onError={() => setImageError(true)}
						/>
					</>
				) : (
					/* Fixed ratio: constrained aspect container with fill */
					<div className={getAspectRatioClass(ratio)}>
						<NextImage
							src={src}
							alt={alt}
							fill
							className={cn(
								"transition-transform duration-300",
								fit === "cover" ? "object-cover" : "object-contain",
								isHovered && "scale-105"
							)}
							unoptimized
							onError={() => setImageError(true)}
						/>
					</div>
				)}

				{/* Hover overlay */}
				<div
					className={cn(
						"absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent",
						"transition-opacity duration-200",
						isHovered ? "opacity-100" : "opacity-0"
					)}
				>
					<div className="absolute bottom-0 left-0 right-0 p-3">
						{title && (
							<h3 className="font-semibold text-white text-sm leading-tight line-clamp-2 mb-0.5">
								{title}
							</h3>
						)}
						{description && (
							<p className="text-white/80 text-xs line-clamp-2 mb-1.5">{description}</p>
						)}
						{displayDomain && (
							<div className="flex items-center gap-1.5">
								{isGenerated ? (
									<SparklesIcon className="size-3.5 text-white/70" />
								) : source?.iconUrl ? (
									<NextImage
										src={source.iconUrl}
										alt={source.label}
										width={14}
										height={14}
										className="rounded"
										unoptimized
									/>
								) : (
									<ExternalLinkIcon className="size-3.5 text-white/70" />
								)}
								<span className="text-white/70 text-xs">{displayDomain}</span>
							</div>
						)}
					</div>
				</div>

				{/* Badge when not hovered */}
				{displayDomain && !isHovered && (
					<div className="absolute bottom-2 right-2">
						<Badge
							variant="secondary"
							className={cn(
								"border-0 text-xs backdrop-blur-sm",
								isGenerated
									? "bg-primary/80 text-primary-foreground"
									: "bg-black/60 text-white"
							)}
						>
							{isGenerated && <SparklesIcon className="size-3 mr-1" />}
							{displayDomain}
						</Badge>
					</div>
				)}
			</div>
		</Card>
	);
}
