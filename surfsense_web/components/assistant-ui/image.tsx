"use client";

import type { ImageMessagePartComponent } from "@assistant-ui/react";
import { cva, type VariantProps } from "class-variance-authority";
import { ImageIcon, ImageOffIcon } from "lucide-react";
import { memo, type PropsWithChildren, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";
import NextImage from 'next/image';

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

type ImagePreviewProps = Omit<React.ComponentProps<"img">, "children"> & {
	containerClassName?: string;
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
	const imgRef = useRef<HTMLImageElement>(null);
	const [loadedSrc, setLoadedSrc] = useState<string | undefined>(undefined);
	const [errorSrc, setErrorSrc] = useState<string | undefined>(undefined);

	const loaded = loadedSrc === src;
	const error = errorSrc === src;

	useEffect(() => {
		if (typeof src === "string" && imgRef.current?.complete && imgRef.current.naturalWidth > 0) {
			setLoadedSrc(src);
		}
	}, [src]);

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
			) : isDataOrBlobUrl(src) ? (
                // biome-ignore lint/performance/noImgElement: data/blob URLs need plain img
                <img
                    ref={imgRef}
                    src={src}
                    alt={alt}
                    className={cn("block h-auto w-full object-contain", !loaded && "invisible", className)}
                    onLoad={(e) => {
                        if (typeof src === "string") setLoadedSrc(src);
                        onLoad?.(e);
                    }}
                    onError={(e) => {
                        if (typeof src === "string") setErrorSrc(src);
                        onError?.(e);
                    }}
                    {...props}
                />
            ) : (
				// biome-ignore lint/performance/noImgElement: intentional for dynamic external URLs
				// <img
				// 	ref={imgRef}
				// 	src={src}
				// 	alt={alt}
				// 	className={cn("block h-auto w-full object-contain", !loaded && "invisible", className)}
				// 	onLoad={(e) => {
				// 		if (typeof src === "string") setLoadedSrc(src);
				// 		onLoad?.(e);
				// 	}}
				// 	onError={(e) => {
				// 		if (typeof src === "string") setErrorSrc(src);
				// 		onError?.(e);
				// 	}}
				// 	{...props}
				// />
				<NextImage
				fill
				src={src || ""}
				alt={alt}
				sizes="(max-width: 768px) 100vw, (max-width: 1200px) 80vw, 60vw"
				className={cn("block object-contain", !loaded && "invisible", className)}
				onLoad={() => {
					if (typeof src === "string") setLoadedSrc(src);
					onLoad?.();
				}}
				onError={() => {
					if (typeof src === "string") setErrorSrc(src);
					onError?.();
				}}
				unoptimized={false}
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
			<button
				type="button"
				onClick={handleOpen}
				className="aui-image-zoom-trigger cursor-zoom-in border-0 bg-transparent p-0 text-left"
				aria-label="Click to zoom image"
			>
				{children}
			</button>
			{isMounted &&
				isOpen &&
				createPortal(
					<button
						type="button"
						data-slot="image-zoom-overlay"
						className="aui-image-zoom-overlay fade-in fixed inset-0 z-50 flex animate-in cursor-zoom-out items-center justify-center border-0 bg-black/80 p-0 duration-200"
						onClick={handleClose}
						aria-label="Close zoomed image"
					>
						{/** biome-ignore lint/performance/noImgElement: <explanation> */}
						{isDataOrBlobUrl(src) ? (
                            // biome-ignore lint/performance/noImgElement: data/blob URLs need plain img
                            <img
                                data-slot="image-zoom-content"
                                src={src}
                                alt={alt}
                                className="aui-image-zoom-content fade-in zoom-in-95 max-h-[90vh] max-w-[90vw] animate-in object-contain duration-200"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    handleClose();
                                }}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter") {
                                        e.stopPropagation();
                                        handleClose();
                                    }
                                }}
                            />
                        ) : (
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
                                unoptimized={false}
                            />
                        )}
					</button>,
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

export { Image, ImageRoot, ImagePreview, ImageFilename, ImageZoom, imageVariants };
