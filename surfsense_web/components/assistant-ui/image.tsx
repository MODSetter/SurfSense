"use client";

import type { ImageMessagePartComponent } from "@assistant-ui/react";
import { cva, type VariantProps } from "class-variance-authority";
import { ImageIcon, ImageOffIcon } from "lucide-react";
import NextImage from "next/image";
import { memo, type PropsWithChildren, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const imageVariants = cva("aui-image-root relative overflow-hidden rounded-lg", {
	variants: {
		variant: {
			outline: "border border-border",
			ghost: "",
			muted: "bg-muted/50",
		},
		size: {
			sm: "max-w-64",
			default: "max-w-96",
			lg: "max-w-[512px]",
			full: "w-full",
		},
	},
	defaultVariants: {
		variant: "outline",
		size: "default",
	},
});

export type ImageRootProps = React.ComponentProps<"div"> & VariantProps<typeof imageVariants>;

function ImageRoot({ className, variant, size, children, ...props }: ImageRootProps) {
	return (
		<div
			data-slot="image-root"
			data-variant={variant}
			data-size={size}
			className={cn(imageVariants({ variant, size, className }))}
			{...props}
		>
			{children}
		</div>
	);
}

type ImagePreviewProps = Omit<
	React.ComponentProps<"img">,
	"children" | "height" | "onError" | "onLoad" | "src" | "width"
> & {
	containerClassName?: string;
	onError?: React.ReactEventHandler<HTMLImageElement>;
	onLoad?: React.ReactEventHandler<HTMLImageElement>;
	src?: string;
};

function ImagePreview({
	className,
	containerClassName,
	onLoad,
	onError,
	alt = "Image content",
	src,
	...props
}: ImagePreviewProps) {
	const [loadedSrc, setLoadedSrc] = useState<string | undefined>(undefined);
	const [errorSrc, setErrorSrc] = useState<string | undefined>(undefined);
	const imageSrc = src ?? "";

	const loaded = imageSrc !== "" && loadedSrc === imageSrc;
	const error = imageSrc === "" || errorSrc === imageSrc;

	useEffect(() => {
		setLoadedSrc((current) => (current === imageSrc ? current : undefined));
		setErrorSrc((current) => (current === imageSrc ? current : undefined));
	}, [imageSrc]);

	return (
		<div data-slot="image-preview" className={cn("relative min-h-32", containerClassName)}>
			{!loaded && !error && (
				<div
					data-slot="image-preview-loading"
					className="absolute inset-0 flex items-center justify-center bg-muted/50"
				>
					<ImageIcon className="size-8 animate-pulse text-muted-foreground" />
				</div>
			)}
			{error ? (
				<div
					data-slot="image-preview-error"
					className="flex min-h-32 items-center justify-center bg-muted/50 p-4"
				>
					<ImageOffIcon className="size-8 text-muted-foreground" />
				</div>
			) : (
				<NextImage
					fill
					src={imageSrc}
					alt={alt}
					sizes="(max-width: 768px) 100vw, (max-width: 1200px) 80vw, 60vw"
					className={cn("block object-contain", !loaded && "invisible", className)}
					onLoad={(event) => {
						setLoadedSrc(imageSrc);
						onLoad?.(event);
					}}
					onError={(event) => {
						setErrorSrc(imageSrc);
						onError?.(event);
					}}
					unoptimized={isDataOrBlobUrl(imageSrc)}
					{...props}
				/>
			)}
		</div>
	);
}

function ImageFilename({ className, children, ...props }: React.ComponentProps<"span">) {
	if (!children) return null;

	return (
		<span
			data-slot="image-filename"
			className={cn("block truncate px-2 py-1.5 text-muted-foreground text-xs", className)}
			{...props}
		>
			{children}
		</span>
	);
}

type ImageZoomProps = PropsWithChildren<{
	src: string;
	alt?: string;
}>;
function isDataOrBlobUrl(src: string | undefined): boolean {
	if (!src || typeof src !== "string") return false;
	return src.startsWith("data:") || src.startsWith("blob:");
}
function ImageZoom({ src, alt = "Image preview", children }: ImageZoomProps) {
	const [isMounted, setIsMounted] = useState(false);
	const [isOpen, setIsOpen] = useState(false);

	useEffect(() => {
		setIsMounted(true);
	}, []);

	const handleOpen = () => setIsOpen(true);
	const handleClose = () => setIsOpen(false);

	useEffect(() => {
		if (!isOpen) return;
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape") setIsOpen(false);
		};
		document.addEventListener("keydown", handleKeyDown);
		return () => document.removeEventListener("keydown", handleKeyDown);
	}, [isOpen]);

	useEffect(() => {
		if (!isOpen) return;
		const originalOverflow = document.body.style.overflow;
		document.body.style.overflow = "hidden";
		return () => {
			document.body.style.overflow = originalOverflow;
		};
	}, [isOpen]);

	return (
		<>
			<Button
				type="button"
				variant="ghost"
				onClick={handleOpen}
				className="aui-image-zoom-trigger h-auto cursor-zoom-in border-0 bg-transparent p-0 text-left hover:bg-transparent"
				aria-label="Click to zoom image"
			>
				{children}
			</Button>
			{isMounted &&
				isOpen &&
				createPortal(
					<Button
						type="button"
						variant="ghost"
						data-slot="image-zoom-overlay"
						className="aui-image-zoom-overlay fade-in fixed inset-0 z-50 h-auto w-auto animate-in cursor-zoom-out items-center justify-center rounded-none border-0 bg-black/80 p-0 duration-200 hover:bg-black/80 focus-visible:ring-0"
						onClick={handleClose}
						aria-label="Close zoomed image"
					>
						<NextImage
							data-slot="image-zoom-content"
							fill
							src={src}
							alt={alt}
							sizes="90vw"
							className="aui-image-zoom-content fade-in zoom-in-95 object-contain duration-200"
							onClick={(e) => {
								e.stopPropagation();
								handleClose();
							}}
							unoptimized={isDataOrBlobUrl(src)}
						/>
					</Button>,
					document.body
				)}
		</>
	);
}

const ImageImpl: ImageMessagePartComponent = ({ image, filename }) => {
	return (
		<ImageRoot>
			<ImageZoom src={image} alt={filename || "Image content"}>
				<ImagePreview src={image} alt={filename || "Image content"} />
			</ImageZoom>
			<ImageFilename>{filename}</ImageFilename>
		</ImageRoot>
	);
};

const Image = memo(ImageImpl) as unknown as ImageMessagePartComponent & {
	Root: typeof ImageRoot;
	Preview: typeof ImagePreview;
	Filename: typeof ImageFilename;
	Zoom: typeof ImageZoom;
};

Image.displayName = "Image";
Image.Root = ImageRoot;
Image.Preview = ImagePreview;
Image.Filename = ImageFilename;
Image.Zoom = ImageZoom;

export { Image, ImageFilename, ImagePreview, ImageRoot, ImageZoom, imageVariants };
