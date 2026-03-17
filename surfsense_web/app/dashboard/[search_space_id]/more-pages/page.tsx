"use client";

import { motion } from "motion/react";
import { MorePagesContent } from "@/components/settings/more-pages-content";

export default function MorePagesPage() {
	return (
		<div className="flex min-h-[calc(100vh-64px)] select-none items-center justify-center px-4 py-8">
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.3 }}
				className="w-full max-w-md space-y-6"
			>
				<MorePagesContent />
			</motion.div>
		</div>
	);
}
