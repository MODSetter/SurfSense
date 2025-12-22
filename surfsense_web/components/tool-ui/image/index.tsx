"use client";

import { ExternalLinkIcon, ImageIcon, Loader2 } from "lucide-react";
import NextImage from "next/image";
import { Component, type ReactNode, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/**
 * Aspect ratio options for images
 */
type AspectRatio = "1:1" | "4:3" | "16:9" | "9:16" | "auto";

/**
 * Image fit options
 */
type ImageFit = "cover" | "contain";

/**
 * Source attribution
 */
interface ImageSource {
	label: string;
	iconUrl?: string;
	url?: string;
}

/**
 * Props for the Image component
 */
export interface ImageProps {
	id: string;
	assetId: string;
	src: string;
	alt: string;
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
 * Serializable schema for Image props (for tool results)
 */
export interface SerializableImage {
	id: string;
	assetId: string;
	src: string;
	alt: string;
	title?: string;
	description?: string;
	href?: string;
	domain?: string;
	ratio?: AspectRatio;
	source?: ImageSource;
}

/**
 * Parse and validate serializable image from tool result
 */
export function parseSerializableImage(result: unknown): SerializableImage {
	if (typeof result !== "object" || result === null) {
		throw new Error("Invalid image result: expected object");
	}

	const obj = result as Record<string, unknown>;

	// Validate required fields
	if (typeof obj.id !== "string") {
		throw new Error("Invalid image: missing id");
	}
	if (typeof obj.assetId !== "string") {
		throw new Error("Invalid image: missing assetId");
	}
	if (typeof obj.src !== "string") {
		throw new Error("Invalid image: missing src");
	}
	if (typeof obj.alt !== "string") {
		throw new Error("Invalid image: missing alt");
	}

	return {
		id: obj.id,
		assetId: obj.assetId,
		src: obj.src,
		alt: obj.alt,
		title: typeof obj.title === "string" ? obj.title : undefined,
		description: typeof obj.description === "string" ? obj.description : undefined,
		href: typeof obj.href === "string" ? obj.href : undefined,
		domain: typeof obj.domain === "string" ? obj.domain : undefined,
		ratio: typeof obj.ratio === "string" ? (obj.ratio as AspectRatio) : undefined,
		source: typeof obj.source === "object" && obj.source !== null ? (obj.source as ImageSource) : undefined,
	};
}

/**
 * Get aspect ratio class based on ratio prop
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
		case "auto":
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
					<div className="aspect-[4/3] bg-muted flex items-center justify-center">
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
export function ImageSkeleton({ maxWidth = "420px" }: { maxWidth?: string }) {
	return (
		<Card className="w-full overflow-hidden animate-pulse" style={{ maxWidth }}>
			<div className="aspect-[4/3] bg-muted flex items-center justify-center">
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
			<div className="aspect-[4/3] bg-muted flex items-center justify-center">
				<div className="flex flex-col items-center gap-3">
					<Loader2 className="size-8 text-muted-foreground animate-spin" />
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
 * Features hover overlay with title and source attribution.
 */
export function Image({
	id,
	src,
	alt,
	title,
	description,
	href,
	domain,
	ratio = "4:3",
	fit = "cover",
	source,
	maxWidth = "420px",
	className,
}: ImageProps) {
	const [isHovered, setIsHovered] = useState(false);
	const [imageError, setImageError] = useState(false);
	const aspectRatioClass = getAspectRatioClass(ratio);
	const displayDomain = domain || source?.label;

	const handleClick = () => {
		const targetUrl = href || source?.url || src;
		if (targetUrl) {
			window.open(targetUrl, "_blank", "noopener,noreferrer");
		}
	};

	if (imageError) {
		return (
			<Card
				id={id}
				className={cn("w-full overflow-hidden", className)}
				style={{ maxWidth }}
			>
				<div className={cn("bg-muted flex items-center justify-center", aspectRatioClass)}>
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
			<div className={cn("relative w-full overflow-hidden bg-muted", aspectRatioClass)}>
				{/* Image */}
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

				{/* Hover overlay - appears on hover */}
				<div
					className={cn(
						"absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent",
						"transition-opacity duration-200",
						isHovered ? "opacity-100" : "opacity-0"
					)}
				>
					{/* Content at bottom */}
					<div className="absolute bottom-0 left-0 right-0 p-4">
						{/* Title */}
						{title && (
							<h3 className="font-semibold text-white text-base leading-tight line-clamp-2 mb-1">
								{title}
							</h3>
						)}

						{/* Description */}
						{description && (
							<p className="text-white/80 text-sm line-clamp-2 mb-2">
								{description}
							</p>
						)}

						{/* Source attribution */}
						{displayDomain && (
							<div className="flex items-center gap-1.5">
								{source?.iconUrl ? (
									<NextImage
										src={source.iconUrl}
										alt={source.label}
										width={16}
										height={16}
										className="rounded"
										unoptimized
									/>
								) : (
									<ExternalLinkIcon className="size-4 text-white/70" />
								)}
								<span className="text-white/70 text-sm">{displayDomain}</span>
							</div>
						)}
					</div>
				</div>

				{/* Always visible domain badge (bottom right, shown when NOT hovered) */}
				{displayDomain && !isHovered && (
					<div className="absolute bottom-2 right-2">
						<Badge 
							variant="secondary" 
							className="bg-black/60 text-white border-0 text-xs backdrop-blur-sm"
						>
							{displayDomain}
						</Badge>
					</div>
				)}
			</div>
		</Card>
	);
}
