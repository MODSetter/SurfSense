"use client";

import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";

function ExpandedGifOverlay({
	src,
	alt,
	onClose,
}: {
	src: string;
	alt: string;
	onClose: () => void;
}) {
	useEffect(() => {
		const handleKey = (e: KeyboardEvent) => {
			if (e.key === "Escape") onClose();
		};
		document.addEventListener("keydown", handleKey);
		return () => document.removeEventListener("keydown", handleKey);
	}, [onClose]);

	return createPortal(
		<motion.div
			initial={{ opacity: 0 }}
			animate={{ opacity: 1 }}
			exit={{ opacity: 0 }}
			transition={{ duration: 0.2 }}
			className="fixed inset-0 z-100 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm sm:p-8"
			onClick={onClose}
		>
			<motion.img
				initial={{ scale: 0.85, opacity: 0 }}
				animate={{ scale: 1, opacity: 1 }}
				exit={{ scale: 0.85, opacity: 0 }}
				transition={{ duration: 0.25, ease: "easeOut" }}
				src={src}
				alt={alt}
				className="max-h-[90vh] max-w-[90vw] cursor-pointer rounded-2xl shadow-2xl"
			/>
		</motion.div>,
		document.body
	);
}

function useExpandedGif() {
	const [expanded, setExpanded] = useState(false);
	const open = useCallback(() => setExpanded(true), []);
	const close = useCallback(() => setExpanded(false), []);
	return { expanded, open, close };
}

export { ExpandedGifOverlay, useExpandedGif };
