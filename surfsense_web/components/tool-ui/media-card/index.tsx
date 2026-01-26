"use client";

import { ExternalLinkIcon, Globe, ImageIcon, LinkIcon } from "lucide-react";
import Image from "next/image";
import { Component, type ReactNode } from "react";
import { z } from "zod";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/**
 * Zod schemas for runtime validation
 */
const AspectRatioSchema = z.enum(["1:1", "4:3", "16:9", "9:16", "21:9", "auto"]);
const MediaCardKindSchema = z.enum(["link", "image", "video", "audio"]);

const ResponseActionSchema = z.object({
	id: z.string(),
	label: z.string(),
	variant: z.enum(["default", "secondary", "outline", "destructive", "ghost"]).nullish(),
	confirmLabel: z.string().nullish(),
});

const SerializableMediaCardSchema = z.object({
	id: z.string(),
	assetId: z.string(),
	kind: MediaCardKindSchema,
	href: z.string().nullish(),
	src: z.string().nullish(),
	title: z.string(),
	description: z.string().nullish(),
	thumb: z.string().nullish(),
	ratio: AspectRatioSchema.nullish(),
	domain: z.string().nullish(),
});

/**
 * Types derived from Zod schemas
 */
type AspectRatio = z.infer<typeof AspectRatioSchema>;
type MediaCardKind = z.infer<typeof MediaCardKindSchema>;
type ResponseAction = z.infer<typeof ResponseActionSchema>;
export type SerializableMediaCard = z.infer<typeof SerializableMediaCardSchema>;

/**
 * Props for the MediaCard component
 */
export interface MediaCardProps {
	id: string;
	assetId: string;
	kind: MediaCardKind;
	href?: string;
	src?: string;
	title: string;
	description?: string;
	thumb?: string;
	ratio?: AspectRatio;
	domain?: string;
	maxWidth?: string;
	alt?: string;
	className?: string;
	responseActions?: ResponseAction[];
	onResponseAction?: (id: string) => void;
}

/**
 * Parse and validate serializable media card from tool result
 */
export function parseSerializableMediaCard(result: unknown): SerializableMediaCard {
	const parsed = SerializableMediaCardSchema.safeParse(result);

	if (!parsed.success) {
		console.warn("Invalid media card data:", parsed.error.issues);
		throw new Error(`Invalid media card: ${parsed.error.issues.map((i) => i.message).join(", ")}`);
	}

	return parsed.data;
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
		case "21:9":
			return "aspect-[21/9]";
		case "auto":
		default:
			return "aspect-[2/1]";
	}
}

/**
 * Get icon based on media card kind
 */
function getKindIcon(kind: MediaCardKind) {
	switch (kind) {
		case "link":
			return <LinkIcon className="size-5" />;
		case "image":
			return <ImageIcon className="size-5" />;
		case "video":
		case "audio":
			return <Globe className="size-5" />;
		default:
			return <LinkIcon className="size-5" />;
	}
}

/**
 * Error boundary for MediaCard
 */
interface MediaCardErrorBoundaryState {
	hasError: boolean;
	error?: Error;
}

export class MediaCardErrorBoundary extends Component<
	{ children: ReactNode },
	MediaCardErrorBoundaryState
> {
	constructor(props: { children: ReactNode }) {
		super(props);
		this.state = { hasError: false };
	}

	static getDerivedStateFromError(error: Error): MediaCardErrorBoundaryState {
		return { hasError: true, error };
	}

	render() {
		if (this.state.hasError) {
			return (
				<Card className="w-full max-w-md border-destructive/20 bg-destructive/5">
					<CardContent className="flex items-center gap-3 p-4">
						<div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-destructive/10">
							<LinkIcon className="size-5 text-destructive" />
						</div>
						<div className="min-w-0 flex-1">
							<p className="font-medium text-destructive text-sm">Failed to load preview</p>
							<p className="text-muted-foreground text-xs truncate">
								{this.state.error?.message || "An error occurred"}
							</p>
						</div>
					</CardContent>
				</Card>
			);
		}

		return this.props.children;
	}
}

/**
 * Loading skeleton for MediaCard
 */
export function MediaCardSkeleton({ maxWidth = "420px" }: { maxWidth?: string }) {
	return (
		<Card className="w-full overflow-hidden animate-pulse" style={{ maxWidth }}>
			<div className="aspect-[2/1] bg-muted" />
			<CardContent className="p-4">
				<div className="h-4 w-3/4 rounded bg-muted" />
				<div className="mt-2 h-3 w-full rounded bg-muted" />
				<div className="mt-1 h-3 w-2/3 rounded bg-muted" />
			</CardContent>
		</Card>
	);
}

/**
 * MediaCard Component
 *
 * A rich media card for displaying link previews, images, and other media
 * in AI chat applications. Supports thumbnails, descriptions, and actions.
 */
export function MediaCard({
	id,
	kind,
	href,
	title,
	description,
	thumb,
	ratio = "auto",
	domain,
	maxWidth = "420px",
	alt,
	className,
	responseActions,
	onResponseAction,
}: MediaCardProps) {
	const aspectRatioClass = getAspectRatioClass(ratio);
	const displayDomain = domain || (href ? new URL(href).hostname.replace("www.", "") : undefined);

	const handleCardClick = () => {
		if (href) {
			window.open(href, "_blank", "noopener,noreferrer");
		}
	};

	return (
		<TooltipProvider>
			<Card
				id={id}
				className={cn(
					"group relative w-full overflow-hidden transition-all duration-200",
					"hover:shadow-lg hover:border-primary/20",
					href && "cursor-pointer",
					className
				)}
				style={{ maxWidth }}
				onClick={href ? handleCardClick : undefined}
				role={href ? "link" : undefined}
				tabIndex={href ? 0 : undefined}
				onKeyDown={(e) => {
					if (href && (e.key === "Enter" || e.key === " ")) {
						e.preventDefault();
						handleCardClick();
					}
				}}
			>
				{/* Thumbnail */}
				{thumb && (
					<div className={cn("relative w-full overflow-hidden bg-muted", aspectRatioClass)}>
						<Image
							src={thumb}
							alt={alt || title}
							fill
							className="object-cover transition-transform duration-300 group-hover:scale-105"
							unoptimized
							onError={(e) => {
								// Hide broken images
								e.currentTarget.style.display = "none";
							}}
						/>
						{/* Gradient overlay */}
						<div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
					</div>
				)}

				{/* Fallback when no thumbnail */}
				{!thumb && (
					<div
						className={cn(
							"relative flex w-full items-center justify-center bg-gradient-to-br from-muted to-muted/50",
							aspectRatioClass
						)}
					>
						<div className="flex flex-col items-center gap-2 text-muted-foreground">
							{getKindIcon(kind)}
							<span className="text-xs">{kind === "link" ? "Link Preview" : kind}</span>
						</div>
					</div>
				)}

				{/* Content */}
				<CardContent className="p-4">
					<div className="flex items-start gap-3">
						{/* Domain favicon placeholder */}
						<div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
							<Globe className="size-5 text-muted-foreground" />
						</div>

						<div className="min-w-0 flex-1">
							{/* Domain badge */}
							{displayDomain && (
								<div className="mb-1.5 flex items-center gap-1.5">
									<Badge variant="secondary" className="text-xs font-normal">
										{displayDomain}
									</Badge>
									{href && (
										<ExternalLinkIcon className="size-3 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
									)}
								</div>
							)}

							{/* Title */}
							<h3 className="font-semibold text-foreground text-sm leading-tight line-clamp-2 group-hover:text-primary transition-colors">
								{title}
							</h3>

							{/* Description */}
							{description && (
								<p className="mt-1.5 text-muted-foreground text-xs leading-relaxed line-clamp-2">
									{description}
								</p>
							)}
						</div>
					</div>

					{/* Response Actions */}
					{responseActions && responseActions.length > 0 && (
						<div className="mt-4 flex items-center justify-end gap-2 border-t pt-3">
							{responseActions.map((action) => (
								<Tooltip key={action.id}>
									<TooltipTrigger asChild>
										<Button
											variant={action.variant || "secondary"}
											size="sm"
											onClick={(e) => {
												e.stopPropagation();
												onResponseAction?.(action.id);
											}}
										>
											{action.label}
										</Button>
									</TooltipTrigger>
									{action.confirmLabel && (
										<TooltipContent>
											<p>{action.confirmLabel}</p>
										</TooltipContent>
									)}
								</Tooltip>
							))}
						</div>
					)}
				</CardContent>
			</Card>
		</TooltipProvider>
	);
}

/**
 * MediaCard Loading State
 */
export function MediaCardLoading({ title = "Loading preview..." }: { title?: string }) {
	return (
		<Card className="w-full max-w-md overflow-hidden">
			<div className="aspect-[2/1] bg-muted animate-pulse flex items-center justify-center">
				<Spinner size="lg" className="text-muted-foreground" />
			</div>
			<CardContent className="p-4">
				<div className="flex items-center gap-3">
					<div className="size-10 rounded-lg bg-muted animate-pulse" />
					<div className="flex-1 space-y-2">
						<div className="h-4 w-3/4 rounded bg-muted animate-pulse" />
						<div className="h-3 w-1/2 rounded bg-muted animate-pulse" />
					</div>
				</div>
				<p className="mt-3 text-center text-muted-foreground text-sm">{title}</p>
			</CardContent>
		</Card>
	);
}
