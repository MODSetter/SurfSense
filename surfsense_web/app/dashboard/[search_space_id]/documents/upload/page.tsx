"use client";

import { Upload } from "lucide-react";
import { motion } from "motion/react";
import { useParams } from "next/navigation";
import { DocumentUploadTab } from "@/components/sources/DocumentUploadTab";

export default function UploadDocumentsPage() {
	const params = useParams();
	const search_space_id = params.search_space_id as string;

	return (
		<div className="container mx-auto py-8 px-4 min-h-[calc(100vh-64px)]">
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
				className="space-y-6"
			>
				{/* Header */}
				<div className="text-center space-y-2">
					<h1 className="text-2xl sm:text-4xl font-bold tracking-tight flex items-center justify-center gap-3">
						<Upload className="h-6 w-6 sm:h-8 sm:w-8" />
						Upload Documents
					</h1>
					<p className="text-muted-foreground text-sm sm:text-lg">
						Upload documents to your search space for AI-powered search and chat
					</p>
				</div>

				{/* Document Upload */}
				<DocumentUploadTab searchSpaceId={search_space_id} />
			</motion.div>
		</div>
	);
}
