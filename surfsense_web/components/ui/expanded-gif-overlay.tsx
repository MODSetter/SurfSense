"use client";

import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

function isVideoSrc(src: string) {
	return /\.(mp4|webm|ogg)(\?|$)/i.test(src);
}

function ExpandedMediaOverlay({
	src,
	alt,
	onClose,
}: {
	src: string;
	alt: string;
	onClose: () => void;
}) {
	const overlayRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		overlayRef.current?.focus();
	}, []);

	useEffect(() => {
		const handleKey = (e: KeyboardEvent) => {
			if (e.key === "Escape") onClose();
		};
		document.addEventListener("keydown", handleKey);
		return () => document.removeEventListener("keydown", handleKey);
	}, [onClose]);

	const mediaElement = isVideoSrc(src) ? (
		<motion.video
			initial={{ scale: 0.85, opacity: 0 }}
			animate={{ scale: 1, opacity: 1 }}
			exit={{ scale: 0.85, opacity: 0 }}
			transition={{ duration: 0.25, ease: "easeOut" }}
			src={src}
			autoPlay
			loop
			muted
			playsInline
			className="max-h-[90vh] max-w-[90vw] cursor-pointer rounded-2xl shadow-2xl"
		/>
	) : (
		<motion.img
			initial={{ scale: 0.85, opacity: 0 }}
			animate={{ scale: 1, opacity: 1 }}
			exit={{ scale: 0.85, opacity: 0 }}
			transition={{ duration: 0.25, ease: "easeOut" }}
			src={src}
			alt={alt}
			className="max-h-[90vh] max-w-[90vw] cursor-pointer rounded-2xl shadow-2xl"
		/>
	);

	return createPortal(
		<motion.div
			role="dialog"
			aria-modal="true"
			aria-label="Expanded media view"
			tabIndex={-1}
			ref={overlayRef}
			initial={{ opacity: 0 }}
			animate={{ opacity: 1 }}
			exit={{ opacity: 0 }}
			transition={{ duration: 0.2 }}
			className="fixed inset-0 z-100 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm sm:p-8"
			onClick={onClose}
			onKeyDown={(e) => {
				if (e.key === "Escape") onClose();
			}}
		>
			{mediaElement}
		</motion.div>,
		document.body
	);
}

function useExpandedMedia() {
	const [expanded, setExpanded] = useState(false);
	const open = useCallback(() => setExpanded(true), []);
	const close = useCallback(() => setExpanded(false), []);
	return { expanded, open, close };
}

/** @deprecated Use ExpandedMediaOverlay instead */
const ExpandedGifOverlay = ExpandedMediaOverlay;
/** @deprecated Use useExpandedMedia instead */
const useExpandedGif = useExpandedMedia;

export { ExpandedMediaOverlay, useExpandedMedia, ExpandedGifOverlay, useExpandedGif };
