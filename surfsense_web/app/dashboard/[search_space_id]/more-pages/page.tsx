"use client";

import { motion } from "motion/react";
import { MorePagesContent } from "@/components/settings/more-pages-content";

export default function MorePagesPage() {
	return (
		<motion.div
			initial={{ opacity: 0, y: 20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.3 }}
			className="w-full select-none space-y-6"
		>
			<MorePagesContent />
		</motion.div>
	);
}
