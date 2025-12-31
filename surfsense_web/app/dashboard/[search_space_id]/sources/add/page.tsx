"use client";

import { Database } from "lucide-react";
import { motion } from "motion/react";
import { useParams } from "next/navigation";
import { ConnectorsTab } from "@/components/sources/ConnectorsTab";

export default function AddSourcesPage() {
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
						<Database className="h-6 w-6 sm:h-8 sm:w-8" />
						Add Sources
					</h1>
					<p className="text-muted-foreground text-sm sm:text-lg">
						Add your sources to your search space
					</p>
				</div>

				{/* Connectors */}
				<div className="mt-8">
					<ConnectorsTab searchSpaceId={search_space_id} />
				</div>
			</motion.div>
		</div>
	);
}
