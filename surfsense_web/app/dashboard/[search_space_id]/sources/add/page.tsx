"use client";

import { IconBrandYoutube } from "@tabler/icons-react";
import { Cable, Database } from "lucide-react";
import { motion } from "motion/react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ConnectorsTab } from "@/components/sources/ConnectorsTab";
import { YouTubeTab } from "@/components/sources/YouTubeTab";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { trackSourcesTabViewed } from "@/lib/posthog/events";

export default function AddSourcesPage() {
	const params = useParams();
	const router = useRouter();
	const searchParams = useSearchParams();
	const search_space_id = params.search_space_id as string;
	const [activeTab, setActiveTab] = useState("youtube");

	// Handle tab from query parameter
	useEffect(() => {
		const tabParam = searchParams.get("tab");
		if (tabParam && ["youtube", "connectors"].includes(tabParam)) {
			setActiveTab(tabParam);
		}
	}, [searchParams]);

	const handleTabChange = (value: string) => {
		setActiveTab(value);
		// Track tab view
		trackSourcesTabViewed(Number(search_space_id), value);
	};

	// Track initial tab view
	useEffect(() => {
		trackSourcesTabViewed(Number(search_space_id), activeTab);
	}, []);

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

				{/* Tabs */}
				<Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
					<TabsList className="grid w-full max-w-2xl mx-auto grid-cols-2 h-12">
						<TabsTrigger value="youtube" className="flex items-center gap-2">
							<IconBrandYoutube className="h-4 w-4" />
							YouTube
						</TabsTrigger>
						<TabsTrigger value="connectors" className="flex items-center gap-2">
							<Cable className="h-4 w-4" />
							<span className="hidden sm:inline">Connectors</span>
							<span className="sm:hidden">More</span>
						</TabsTrigger>
					</TabsList>

					<div className="mt-8">
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
