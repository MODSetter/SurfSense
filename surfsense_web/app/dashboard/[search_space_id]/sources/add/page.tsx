"use client";

import { IconBrandYoutube } from "@tabler/icons-react";
import { Cable, Database, Upload } from "lucide-react";
import { motion } from "motion/react";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ConnectorsTab } from "@/components/sources/ConnectorsTab";
import { DocumentUploadTab } from "@/components/sources/DocumentUploadTab";
import { YouTubeTab } from "@/components/sources/YouTubeTab";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function AddSourcesPage() {
	const params = useParams();
	const searchParams = useSearchParams();
	const search_space_id = params.search_space_id as string;
	const [activeTab, setActiveTab] = useState("documents");

	// Handle tab from query parameter
	useEffect(() => {
		const tabParam = searchParams.get("tab");
		if (tabParam && ["documents", "youtube", "connectors"].includes(tabParam)) {
			setActiveTab(tabParam);
		}
	}, [searchParams]);

	return (
		<div className="container mx-auto py-8 px-4">
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
				className="space-y-6"
			>
				{/* Header */}
				<div className="text-center space-y-2">
					<h1 className="text-4xl font-bold tracking-tight flex items-center justify-center gap-3">
						<Database className="h-8 w-8" />
						Add Sources
					</h1>
					<p className="text-muted-foreground text-lg">Add your sources to your search space</p>
				</div>

				{/* Tabs */}
				<Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
					<TabsList className="grid w-full max-w-2xl mx-auto grid-cols-3 h-12">
						<TabsTrigger value="documents" className="flex items-center gap-2">
							<Upload className="h-4 w-4" />
							Documents
						</TabsTrigger>
						<TabsTrigger value="youtube" className="flex items-center gap-2">
							<IconBrandYoutube className="h-4 w-4" />
							YouTube
						</TabsTrigger>
						<TabsTrigger value="connectors" className="flex items-center gap-2">
							<Cable className="h-4 w-4" />
							Connectors
						</TabsTrigger>
					</TabsList>

					<div className="mt-8">
						<TabsContent value="documents" className="space-y-6">
							<DocumentUploadTab searchSpaceId={search_space_id} />
						</TabsContent>

						<TabsContent value="youtube" className="space-y-6">
							<YouTubeTab searchSpaceId={search_space_id} />
						</TabsContent>

						<TabsContent value="connectors" className="space-y-6">
							<ConnectorsTab searchSpaceId={search_space_id} />
						</TabsContent>
					</div>
				</Tabs>
			</motion.div>
		</div>
	);
}
